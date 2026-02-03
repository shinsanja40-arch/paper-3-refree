"""
Proven Fact-Based Algorithm for AI Training
Complete Implementation with All Bug Fixes and Enhancements

Version: 1.4.0-ABSOLUTE-FINAL
Date: 2026-02-03
Status: Production Ready

LICENSE:
BY-NC (Personal use allowed. Commercial use prohibited. Attribution required.)
Copyright (c) 2026 [Cheongwon Choi]

Permission is hereby granted, free of charge for personal and non-commercial use only, 
to any person obtaining a copy of this software and associated documentation files 
(the "Software"), subject to the following conditions:

Attribution: The above copyright notice and this permission notice (including the 
author's name) shall be included in all copies or substantial portions of the Software.

Non-Commercial Use: The Software may not be used, copied, modified, merged, published, 
distributed, or sold for any commercial purposes. Commercial use of the Software without 
prior written permission from the copyright holder is strictly prohibited.

No Warranty: THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. 
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, 
DAMAGES OR OTHER LIABILITY.

=== CHANGELOG ===

v1.4.0 (2026-02-03):
  [Gemini 제안 검증 및 수용]
  - C2: confirmed_logic 오염 방지 – pending_logic 스테이징 버퍼 도입
        (세션 종료 시 즉시 confirmed에 넣지 않음. 다음 세션도 clean이면 승격.
         할루시네이션 발견 시 pending 폐기 → 오염 경로 완전 차단)
  - Gemini H1 (TMO-1), H2 (_manage_context_window), M1 (save_results makedirs),
    M2 (referee schedule formula) — 모두 이미 수정됨 확인

  [Grok 제안 검증 및 수용]
  - CRITICAL-1: anthropic / openai ImportError 가드 추가
        (미설치 시 명확한 설치 안내 후 종료)
  - CRITICAL-2 (API key), CRITICAL-3 (infinite loop), HIGH-4~5, LOW-2
    — 모두 이미 수정됨 확인

  [독립 분석으로 추가 발견된 버그 수정]
  - BUG-NEW-1: count_tokens docstring ÷3.8 → ÷4로 정합성 수정
  - BUG-NEW-2: student.ask_question(professors_explanation="\n\n".join([f"Prof {i+1}: {r}" for i,r in enumerate(professor_responses)]) if professor_responses else "")
        학생이 교수 응답을 전혀 보지 못하는 CRITICAL 논리 버그.
        professor_responses를 턴 루프 외부로 선언하여 이전 턴 응답을 학생에게 전달
  - BUG-NEW-3: README "python proven_fact_system.py" → "python run_proven_fact.py"
  - BUG-NEW-4: README JSON 출력 스키마 실제 코드와 완전 불일치 → 수정
  - BUG-NEW-5: README 코드 예제 metrics['hallucination_rate'] → KeyError 수정
  - BUG-NEW-6: README badge bugs_fixed 19 → 실제 변경 수로 갱신
  - BUG-NEW-7: _detect_loop 임계값 >5 → >3 (10단어 문자열에서 >5는 실질적 불가)

v1.2.0 (2026-02-03):
  [제안 수용]
  - SUGGEST-01: Force-Proceed 플래그 - 교착 2회 이상 시 교수 판정승으로 강제종료
  - SUGGEST-02: Anachronism 개념 침투 감지 강화 - 금지어 기반이 아닌 시대별 개념 체크
  - SUGGEST-03: Student confirmed_logic 참조 구현 - 확정된 논리에 대한 반박 방지
  - SUGGEST-04: tiktoken 기반 실제 토큰 수 계산 (fallback 포함)
  - SUGGEST-05: Exponential Backoff 재시도 로직 - API 호출 안정성
  - SUGGEST-06: Post-reset briefing에 current_stage_evidence 포함

  [추가 발견 버그 수정]
  - BUG-A: run_proven_fact.py 심판 주기 설명 텍스트 불일치 수정
  - BUG-B: _create_personas() schedule 안내 print 불일치 수정
  - BUG-C: analyze_proven_fact.py referee_analysis 이전 주기 사용 수정
  - BUG-D: conflict 해결 중간 턴에서 record_exchange() 건너뛰기 수정
  - BUG-E: _resolve_referee_conflict() 반환 hallucination에 session 필드 누락 수정
  - BUG-F: ValidationSpecialist resolve_deadlock() 메서드 구현 완료
  - BUG-G: _manage_context_window() 호출 누락 수정 (_call_api 직전에 호출)
  - BUG-H: key_evidence를 teach()/ask_question() prompt에 inject 수정
  - BUG-I: update_stage()의 split("FORBIDDEN VOCABULARY") 엣지 케이스 수정

v1.1.0 (2026-02-03):
  - Reset schedule: 5n,5n-3 (2명) / 7n,7n-3,7n-5 (3명)
  - BUG-020: Token overflow + Key Evidence preservation
  - BUG-021: Referee deadlock (ValidationSpecialist)
  - BUG-022: Student infinite rebuttal (confirmed_logic)
  - Post-reset briefing, Redundancy detection

v1.0.0:
  - Initial release with 19 bug fixes
"""

import json
import time
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import logging
import sys
import os

# ---------------------------------------------------------------------------
# API 클라이언트 라이브러리 — 미설치 시 명확한 안내 출력
# ---------------------------------------------------------------------------
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False
    anthropic = None  # type: ignore[assignment]

try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    openai = None  # type: ignore[assignment]

if not _ANTHROPIC_AVAILABLE and not _OPENAI_AVAILABLE:
    print("=" * 70)
    print("  ❌ FATAL: No API client library installed")
    print("=" * 70)
    print()
    print("  At least one of the following packages is required:")
    print()
    print("    pip install anthropic      # for Claude")
    print("    pip install openai         # for GPT-4")
    print()
    print("=" * 70)
    sys.exit(1)

# ---------------------------------------------------------------------------
# SUGGEST-04: tiktoken 토큰 수 계산 (fallback 포함)
# ---------------------------------------------------------------------------
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
    _tiktoken_enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 / Claude 호환
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    _tiktoken_enc = None
    print("=" * 70)
    print("  ⚠️  WARNING: tiktoken not installed")
    print("=" * 70)
    print()
    print("  The system will use approximate token counting (÷4).")
    print("  For accurate token counts, install tiktoken:")
    print()
    print("    pip install tiktoken")
    print()
    print("=" * 70)
    print()
# 한국어 형태소 분석기 (GROK-H2)
try:
    from konlpy.tag import Okt
    _KONLPY_AVAILABLE = True
    _okt = Okt()
except ImportError:
    _KONLPY_AVAILABLE = False
    _okt = None



def count_tokens(text: str) -> int:
    """
    실제 토큰 수를 계산한다.

    우선순위:
      1. tiktoken 설치됨            → 정확한 값 반환
      2. konlpy 설치됨 + 한글 포함   → 형태소 수 기반 추정 (morphs * 1.3)
      3. fallback                    → len(text) // 4
    """
    if _TIKTOKEN_AVAILABLE and _tiktoken_enc is not None:
        return len(_tiktoken_enc.encode(text))

    # konlpy 경로: 한글이 포함되어 있는 경우에만 사용
    if _KONLPY_AVAILABLE and _okt is not None:
        # 한글 범위 U+AC00 ~ U+D7A3 내 문자가 하나라도 있으면 한글 텍스트로 판단
        has_korean = any('\uac00' <= ch <= '\ud7a3' for ch in text)
        if has_korean:
            try:
                morphs = _okt.morphs(text)
                # 형태소 수에 ~1.3배 보정 (서브토큰 분할 고려)
                return max(1, int(len(morphs) * 1.3))
            except Exception:
                pass  # konlpy 실행 오류 시 fallback으로 통과

    # fallback: 평균 ~4 chars/token
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Referee schedule 생성
# ---------------------------------------------------------------------------
def generate_referee_schedules(num_referees: int, max_sessions: int = 200) -> List[List[int]]:
    """
    Generate non-overlapping reset schedules for referees.

    v1.1.0 SCHEDULE:
      2 referees: 5n, 5n-3   →  R1: 5,10,15,20…  /  R2: 2,7,12,17…
      3 referees: 7n, 7n-3, 7n-5  →  R1: 7,14,21… / R2: 4,11,18… / R3: 2,9,16…

    Guarantees:
      • Zero simultaneous resets
      • First reset at session 2 (early bias prevention)
      • Uniform coverage across the full run
    """
    if num_referees == 2:
        s1 = [5 * n for n in range(1, max_sessions // 5 + 2) if 5 * n <= max_sessions]
        s2 = [5 * n - 3 for n in range(1, max_sessions // 5 + 2) if 0 < 5 * n - 3 <= max_sessions]
        return [s1, s2]

    elif num_referees == 3:
        s1 = [7 * n for n in range(1, max_sessions // 7 + 2) if 7 * n <= max_sessions]
        s2 = [7 * n - 3 for n in range(1, max_sessions // 7 + 2) if 0 < 7 * n - 3 <= max_sessions]
        s3 = [7 * n - 5 for n in range(1, max_sessions // 7 + 2) if 0 < 7 * n - 5 <= max_sessions]
        return [s1, s2, s3]

    else:
        raise ValueError(f"Only 2 or 3 referees supported, got {num_referees}")


# ---------------------------------------------------------------------------
# PersonaAgent – 기본 클래스
# ---------------------------------------------------------------------------
class PersonaAgent:
    """
    Base class for all persona agents.

    FIX BUG-020 : key_evidence 보존 + _manage_context_window()
    SUGGEST-04  : tiktoken 기반 토큰 계산
    SUGGEST-05  : Exponential Backoff retry
    BUG-G       : _manage_context_window() 호출 – _call_api 직전에 실행
    BUG-H       : key_evidence를 프롬프트에 inject
    """

    # Exponential backoff 설정
    MAX_RETRIES = 3
    BASE_DELAY_SEC = 1.0
    MAX_DELAY_SEC = 30.0

    def __init__(self, name: str, role: str, client, system_prompt: str):
        self.name = name
        self.role = role
        self.client = client
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict] = []

        # BUG-020 / BUG-G / BUG-H
        self.key_evidence: List[str] = []
        self.max_history_size = 10          # 최대 10개 교환 유지

    # ------------------------------------------------------------------
    def inject_constants(self, constants_str: str):
        if constants_str and "FIXED PHYSICAL CONSTANTS" not in self.system_prompt:
            self.system_prompt += f"\n\n{constants_str}"

    # ------------------------------------------------------------------
    # BUG-020 key_evidence
    def add_key_evidence(self, evidence: str):
        """핵심 증거를 등록한다. 컨텍스트 압축 후에도 유지된다."""
        if evidence and evidence not in self.key_evidence:
            self.key_evidence.append(evidence)
            if len(self.key_evidence) > 20:
                self.key_evidence = self.key_evidence[-20:]

    # ------------------------------------------------------------------
    # BUG-G : _manage_context_window – _call_api 직전에 반드시 호출
    def _manage_context_window(self):
        """컨텍스트 윈도우 압축 (처음 2 + 마지막 (max-2)만 유지)"""
        if len(self.conversation_history) > self.max_history_size:
            keep_recent = self.max_history_size - 2
            self.conversation_history = (
                self.conversation_history[:2] +
                self.conversation_history[-keep_recent:]
            )

    # ------------------------------------------------------------------
    # BUG-H : key_evidence inject helper
    def _build_key_evidence_str(self) -> str:
        """프롬프트에 삽입할 핵심 증거 문자열을 반환한다."""
        if not self.key_evidence:
            return ""
        lines = "\n".join(f"  • {ev}" for ev in self.key_evidence)
        return (
            "\n\n⭐ KEY EVIDENCE (permanently preserved – always consider these):\n"
            + lines + "\n"
        )

    # ------------------------------------------------------------------
    # SUGGEST-05 : Exponential Backoff retry
    # TMO-1    : timeout 파라미터 추가
    def _call_api(self, user_message: str, temperature: float = 0.7,
                  timeout: int = 120) -> str:
        """
        Call LLM API with Exponential Backoff retry.
        최대 MAX_RETRIES회 재시도. 모두 실패하면 [API ERROR] 반환.
        TMO-1: 개별 호출당 timeout(기본 120초) 적용.
        """
        # BUG-G : 호출 직전에 컨텍스트 압축
        self._manage_context_window()

        messages = [{"role": "user", "content": user_message}]

        for attempt in range(self.MAX_RETRIES + 1):          # 0 … MAX_RETRIES
            try:
                if _ANTHROPIC_AVAILABLE and isinstance(self.client, anthropic.Anthropic):
                    response = self.client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4096,
                        temperature=temperature,
                        system=self.system_prompt,
                        messages=messages,
                        timeout=timeout                         # TMO-1
                    )
                    return response.content[0].text

                else:  # OpenAI
                    oai_messages = [
                        {"role": "system", "content": self.system_prompt}
                    ] + messages
                    response = self.client.chat.completions.create(
                        model="gpt-4",
                        messages=oai_messages,
                        temperature=temperature,
                        max_tokens=4096,
                        timeout=timeout                         # TMO-1
                    )
                    return response.choices[0].message.content

            except (TimeoutError, ConnectionError) as e:
                # 타임아웃 / 연결 에러는 항상 재시도 가능
                if attempt < self.MAX_RETRIES:
                    delay = min(
                        self.BASE_DELAY_SEC * (2 ** attempt) + random.uniform(0, 1),
                        self.MAX_DELAY_SEC
                    )
                    print(f"  ⚠️  [{self.name}] Timeout/Connection error (attempt {attempt+1}/{self.MAX_RETRIES+1}): "
                          f"{e}  → retry in {delay:.1f}s")
                    time.sleep(delay)
                else:
                    print(f"  ❌ [{self.name}] Timeout/Connection failed after {self.MAX_RETRIES+1} attempts: {e}")
                    return f"[API ERROR after {self.MAX_RETRIES+1} retries: {str(e)}]"

            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    delay = min(
                        self.BASE_DELAY_SEC * (2 ** attempt) + random.uniform(0, 1),
                        self.MAX_DELAY_SEC
                    )
                    print(f"  ⚠️  [{self.name}] API error (attempt {attempt+1}/{self.MAX_RETRIES+1}): "
                          f"{e}  → retry in {delay:.1f}s")
                    time.sleep(delay)
                else:
                    print(f"  ❌ [{self.name}] API failed after {self.MAX_RETRIES+1} attempts: {e}")
                    return f"[API ERROR after {self.MAX_RETRIES+1} retries: {str(e)}]"

        return "[API ERROR: unexpected]"   # unreachable but safe


# ===========================================================================
# ProfessorAgent
# ===========================================================================
class ProfessorAgent(PersonaAgent):
    """
    Professor persona with domain expertise.

    SUGGEST-02 : era-concept awareness (개념 침투 감지)
    BUG-H      : key_evidence를 teach() prompt에 inject
    BUG-I      : update_stage() split 엣지 케이스 수정
    """

    # 시대별 금지 "개념" 목록 (단어가 아닌 개념 단위)
    ERA_CONCEPT_RESTRICTIONS: Dict[int, List[str]] = {
        1: [
            "gravity / gravitational force (만유인력)",
            "mass-dependent attraction (질량에 비례하는 인력)",
            "atoms / molecules (원자·분자)",
            "electromagnetic spectrum (전자기 스펙트럼)",
            "quantum mechanics (양자역학)",
            "relativity (상대론)",
            "inertia as formalized physics (관성의 수학적 공식화)",
        ],
        2: [
            "atoms / molecules (원자·분자)",
            "electromagnetic spectrum (전자기 스펙트럼)",
            "quantum mechanics (양자역학)",
            "relativity (상대론)",
            "subatomic particles (소립자)",
        ],
        3: [
            "quantum mechanics (양자역학)",
            "relativity (상대론)",
            "subatomic particles (소립자)",
        ],
        4: []   # 제한 없음
    }

    def __init__(self, name: str, specialty: str, client, current_stage: int = 1):
        forbidden_vocab = self._get_forbidden_vocabulary(current_stage)
        concept_check = self._get_concept_restriction_prompt(current_stage)

        system_prompt = f"""You are Professor {name}, a world-class expert in {specialty}.

YOUR ONLY MISSION:
- Convince the REFEREES with solid, multi-sourced evidence
- The referees are your ONLY judges
- Provide at least 3-5 independent sources for each claim
- Explain the proven fact using ONLY evidence available in the current era
- Be rigorous and precise in your reasoning
- Challenge the student's misconceptions constructively
- Maintain consistency with other professors' explanations

{forbidden_vocab}

{concept_check}

CRITICAL REQUIREMENT - MINIMUM REBUTTALS:
You must provide at least 4 distinct rebuttals or clarifications per exchange.
Format them as numbered points: 1. [rebuttal], 2. [rebuttal], etc.

LOGICAL CONSISTENCY:
- Build upon previous professors' arguments
- Do NOT contradict established facts from earlier sessions
- If you notice an inconsistency, acknowledge and resolve it

RESPONSE STYLE:
- Be clear and pedagogical
- Use Socratic questioning when appropriate
- Provide specific examples and evidence
- Never use approximations when exact values are available

EXTERNAL VERIFICATION REQUIREMENT (ENHANCED):
When making factual claims, especially numerical or historical:
1. Cross-reference multiple independent sources (minimum 3-5 sources)
2. Explicitly state the verification method used
3. If sources conflict, acknowledge and explain the discrepancy
4. Prioritize primary sources over secondary interpretations
5. Be transparent about uncertainty levels

RESPONDING TO REFEREE CHALLENGES:
If a referee flags your statement:
1. Carefully review the specific claim challenged
2. Provide detailed evidence from multiple independent sources
3. Show your reasoning process step-by-step
4. If you were incorrect, explicitly acknowledge and correct
5. NEVER defend an error - intellectual honesty is paramount
"""
        super().__init__(name, "Professor", client, system_prompt)
        self.specialty = specialty
        self.current_stage = current_stage
        # BUG-I : base_system_prompt는 FORBIDDEN/CONCEPT 블록 이전까지만 저장
        self._base_prompt_core = self._extract_base_core(system_prompt)
        self.previous_arguments: List[str] = []

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_base_core(prompt: str) -> str:
        """FORBIDDEN VOCABULARY 블록 이전의 고정 부분만 추출"""
        # 두 sentinel 중 먼저 나타나는 곳까지만 유지
        for marker in ("FORBIDDEN VOCABULARY", "⚠️ ERA-CONCEPT RESTRICTION"):
            idx = prompt.find(marker)
            if idx != -1:
                return prompt[:idx]
        return prompt   # sentinel이 없으면 전체 반환

    # ------------------------------------------------------------------
    def _get_forbidden_vocabulary(self, stage: int) -> str:
        restrictions = {
            1: ["gravity", "atom", "molecule", "electron", "quantum",
                "relativity", "telescope", "microscope", "spectrum"],
            2: ["atom", "molecule", "electron", "quantum",
                "relativity", "spectrum", "electromagnetic"],
            3: ["quantum", "relativity", "subatomic"],
            4: []
        }
        forbidden = restrictions.get(stage, [])
        if forbidden:
            return (
                "FORBIDDEN VOCABULARY (not available in this era):\n"
                + ", ".join(forbidden) + "\n"
                "DO NOT use these terms. Use only concepts available in this historical period."
            )
        return ""

    # ------------------------------------------------------------------
    # SUGGEST-02 : 개념 침투 감지용 프롬프트
    def _get_concept_restriction_prompt(self, stage: int) -> str:
        concepts = self.ERA_CONCEPT_RESTRICTIONS.get(stage, [])
        if not concepts:
            return ""
        lines = "\n".join(f"  - {c}" for c in concepts)
        return (
            "⚠️ ERA-CONCEPT RESTRICTION (단어가 아닌 '개념' 자체도 금지):\n"
            "The following CONCEPTS did not exist in this era. "
            "Do NOT explain or imply them in any form, even indirectly:\n"
            + lines + "\n"
            "Example violation: saying 'force proportional to mass' in Stage 1 "
            "is a concept anachronism even though the word 'gravity' is absent.\n"
        )

    # ------------------------------------------------------------------
    # BUG-I 수정 : update_stage – split 대신 저장된 core 사용
    def update_stage(self, new_stage: int):
        self.current_stage = new_stage
        forbidden_vocab = self._get_forbidden_vocabulary(new_stage)
        concept_check = self._get_concept_restriction_prompt(new_stage)

        self.system_prompt = self._base_prompt_core
        if forbidden_vocab:
            self.system_prompt += "\n\n" + forbidden_vocab
        if concept_check:
            self.system_prompt += "\n\n" + concept_check

        bridge = (
            f"\n\n🔄 STAGE TRANSITION TO {new_stage}:\n"
            "- Build upon conclusions from previous stages\n"
            "- DO NOT regress to earlier limitations\n"
            "- Integrate new evidence with established understanding\n"
            "- Maintain logical continuity\n"
        )
        self.system_prompt += bridge
        print(f"  🔄 {self.name} updated to Stage {new_stage}")

    # ------------------------------------------------------------------
    # BUG-H : teach()에 key_evidence inject
    def teach(self, student_question: str, context: str = "",
              available_evidence: List[str] = None,
              consistency_reminder: str = "") -> str:

        evidence_str = ""
        if available_evidence:
            evidence_str = "\n\nAVAILABLE EVIDENCE (use these):\n"
            evidence_str += "\n".join(f"- {ev}" for ev in available_evidence)

        # key_evidence inject
        key_ev_str = self._build_key_evidence_str()

        prompt = f"""{consistency_reminder}

CONTEXT: {context}
{key_ev_str}
STUDENT'S QUESTION/CHALLENGE:
{student_question}

{evidence_str}

Provide your pedagogical response with at least 4 numbered rebuttals/clarifications.
Use EXACT values from fixed constants. Cite specific evidence.
"""
        response = self._call_api(prompt, temperature=0.7)

        # 핵심 증거 자동 추출 – 숫자가 포함된 문장을 key evidence로 등록
        for line in response.split('\n'):
            line = line.strip()
            if any(ch.isdigit() for ch in line) and len(line) > 30:
                self.add_key_evidence(line[:200])   # 최대 200자

        self.previous_arguments.append(response)
        self.conversation_history.append({
            "student": student_question,
            "professor": response
        })
        return response

    # ------------------------------------------------------------------
    def defend_against_referee(self, challenged_statement: str,
                               referee_reasoning: str,
                               fixed_constants: Dict) -> Dict:
        constants_str = ""
        if fixed_constants:
            constants_str = "\n\nFIXED CONSTANTS:\n"
            for key, val in fixed_constants.items():
                constants_str += f"- {key}: {val}\n"

        key_ev_str = self._build_key_evidence_str()

        prompt = f"""A referee has challenged your statement:

CHALLENGED STATEMENT:
{challenged_statement}

REFEREE'S REASONING:
{referee_reasoning}

{constants_str}
{key_ev_str}

You must respond with:
1. Do you acknowledge an error? (Yes/No and why)
2. If No: Provide evidence from at least 3-5 independent sources
3. If Yes: Provide the corrected statement
4. Show your verification process

Format your response as JSON:
{{
    "acknowledges_error": true/false,
    "defense": "your detailed defense or acknowledgment",
    "sources": ["source 1", "source 2", ...],
    "corrected_statement": "corrected version if applicable"
}}
"""
        response_text = self._call_api(prompt, temperature=0.3)

        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parse error in {self.name}.defend_against_referee: {e}")
            return {
                "acknowledges_error": False,
                "defense": response_text,
                "sources": [],
                "corrected_statement": "",
                "parse_error": str(e)
            }
        except Exception:
            return {
                "acknowledges_error": False,
                "defense": response_text,
                "sources": [],
                "corrected_statement": ""
            }


# ===========================================================================
# StudentAgent
# ===========================================================================
class StudentAgent(PersonaAgent):
    """
    Skeptical student persona.

    SUGGEST-03 : confirmed_logic를 받아 프롬프트에 주입 → 무한 반박 방지
    BUG-H      : key_evidence inject
    """

    def __init__(self, name: str, client, skepticism_level: str = "ultra-high"):
        system_prompt = f"""You are {name}, an extremely intelligent but deeply skeptical student.

YOUR MISSION:
- Challenge EVERY claim with rigorous logical scrutiny
- Ask probing questions that test the limits of professors' arguments
- Do NOT accept explanations easily - maintain skepticism for at least 3 exchanges
- Point out potential flaws, alternative explanations, or missing evidence
- Be respectful but relentless in your pursuit of truth

SKEPTICISM LEVEL: {skepticism_level}

CRITICAL REQUIREMENT - MINIMUM QUESTIONS:
You MUST ask at least 4 distinct questions or challenges per exchange.
Format: 1. [question], 2. [question], 3. [question], 4. [question]

IMPORTANT - AVOID FAKE SURRENDER:
When you acknowledge a professor's point, you must EXPLICITLY:
1. State which specific argument convinced you
2. Explain the logical connection you now understand
3. Acknowledge remaining uncertainties
4. If you have no remaining doubts, say so clearly

NEVER say "I understand" without explaining WHAT you understand and WHY.

INTELLECTUAL HONESTY:
- If caught in an error, explicitly withdraw your false claim
- Distinguish between "I'm not convinced yet" vs "I was wrong"
- Track your own previous arguments and avoid circular reasoning
"""
        super().__init__(name, "Student", client, system_prompt)
        self.challenged_claims: List[str] = []
        self.error_history: List[str] = []
        self.confirmed_logic_ids: set = set()   # SUGGEST-03

    # ------------------------------------------------------------------
    # SUGGEST-03 : confirmed_logic 업데이트
    def update_confirmed_logic(self, confirmed_logic: List[Dict]):
        """심판이 확정한 논리 노드들을 학생에게 전달한다."""
        for node in confirmed_logic:
            conclusion = node.get('conclusion', '')
            if conclusion:
                self.confirmed_logic_ids.add(conclusion)

    # ------------------------------------------------------------------
    # SUGGEST-03 + BUG-H
    def ask_question(self, professors_explanation: str, context: str = "",
                     minimum_questions: int = 4,
                     previous_errors: List[str] = None,
                     confirmed_logic: List[Dict] = None) -> str:

        # ---- error context ----
        error_context = ""
        if previous_errors:
            error_context = (
                "\n⚠️ CRITICAL - YOUR PREVIOUS ERRORS TO ADDRESS:\n"
                + "\n".join(f"- {err}" for err in previous_errors)
                + "\n\nYou MUST explicitly withdraw these false claims before proceeding.\n"
                "Use phrases like: \"I was incorrect when I claimed…\"\n"
            )

        # ---- SUGGEST-03 : confirmed_logic 주입 ----
        confirmed_str = ""
        if confirmed_logic:
            self.update_confirmed_logic(confirmed_logic)

        if self.confirmed_logic_ids:
            items = "\n".join(f"  • {c}" for c in list(self.confirmed_logic_ids)[-15:])
            confirmed_str = (
                "\n\n📌 CONFIRMED LOGIC (심판이 확정한 사실 – 반박하지 DO NOT repeat these challenges):\n"
                + items + "\n\n"
                "RULE: Do NOT re-challenge the above conclusions.\n"
                "INSTEAD: Attack the NEXT logical step / implication / weakness "
                "that BUILDS ON the confirmed facts.\n"
                "Bad example: \"But how do we know the Earth is round?\" (already confirmed)\n"
                "Good example: \"Given Earth is round, how does this affect ancient navigation?\"\n"
            )

        # ---- key_evidence ----
        key_ev_str = self._build_key_evidence_str()

        prompt = f"""{error_context}

CONTEXT: {context}
{key_ev_str}{confirmed_str}
PROFESSORS' EXPLANATIONS:
{professors_explanation}

Generate at least {minimum_questions} distinct, numbered questions or challenges.
Be thoroughly skeptical - don't accept claims at face value.
If you do accept a point, explain PRECISELY what convinced you and why.
"""
        response = self._call_api(prompt, temperature=0.8)

        # 최소 질문 수 검증
        numbered = [l for l in response.split('\n')
                    if l.strip() and l.strip()[0].isdigit() and '. ' in l]
        if len(numbered) < minimum_questions:
            print(f"  ⚠️ Student provided only {len(numbered)}/{minimum_questions} questions. Requesting more…")
            followup = (
                f"You provided only {len(numbered)} questions, but {minimum_questions} are required.\n"
                f"Please provide {minimum_questions - len(numbered)} additional distinct challenges."
            )
            response += "\n\n" + self._call_api(followup, temperature=0.9)

        self.conversation_history.append({
            "professors": professors_explanation,
            "student": response
        })
        return response


# ===========================================================================
# RefereeAgent
# ===========================================================================
class RefereeAgent(PersonaAgent):
    """
    Independent referee for hallucination detection.

    SUGGEST-02 : 개념 침투 감지 체크 포함
    SUGGEST-06 : reset 시 current_stage_evidence 주입
    """

    def __init__(self, name: str, client, reset_schedule: List[int],
                 strictness: str = "high"):

        system_prompt = f"""You are {name}, an absolutely impartial referee and fact-checker.

YOUR MISSION:
- Verify EVERY factual claim made by professors
- Detect and flag hallucinations, exaggerations, or approximations
- Maintain independence - no bias toward any participant
- Apply ZERO TOLERANCE for approximations when exact values exist

STRICTNESS LEVEL: {strictness}

HALLUCINATION DETECTION CATEGORIES:
1. Factual Error: Objectively false statement
2. Anachronistic Vocabulary: Using terms not available in current evidence stage
3. ⭐ Anachronistic CONCEPT: Using a CONCEPT that did not exist in this era,
   even if the forbidden word itself is not used.
   Example: Describing "force proportional to mass" in Stage 1 (pre-Newton)
   is a concept anachronism.
4. Approximation When Exact Value Exists: Using "~" or "about" for fixed constants
5. Logical Fallacy: Invalid reasoning structure
6. Contradicting Established Facts: Conflicting with previously proven points

FOR STUDENT ERRORS:
- Allow professors to correct first (2 rounds maximum)
- Only intervene if professors fail to catch student's hallucination after 2 exchanges

SEVERITY LEVELS:
- critical: Undermines core argument
- high: Significant factual error
- medium: Minor inaccuracy
- low: Stylistic or trivial issue

IMPORTANT: Referees can make errors too. When challenged by professors with 
strong evidence from multiple sources, be willing to reconsider your assessment.
"""
        super().__init__(name, "Referee", client, system_prompt)

        self.base_system_prompt = system_prompt
        self.injected_constants = ""
        self.confirmed_logic: List[Dict] = []

        self.reset_schedule = reset_schedule
        self.reset_count = 0
        self.strictness = strictness
        self.student_error_tracker: Dict[str, int] = defaultdict(int)

        # SUGGEST-06 : 현재 스테이지 증거 저장 (reset 시 주입용)
        self.current_stage_evidence: List[str] = []
        self.current_stage_num: int = 1

    # ------------------------------------------------------------------
    def inject_constants(self, constants_str: str):
        self.injected_constants = constants_str
        self.system_prompt = self.base_system_prompt + "\n\n" + constants_str

    # ------------------------------------------------------------------
    def add_confirmed_logic(self, logic_node: Dict):
        """세션 완료 후 확정된 논리 노드를 심판에게 추가"""
        self.confirmed_logic.append(logic_node)

    # ------------------------------------------------------------------
    # SUGGEST-06 : stage 증거 업데이트
    def update_current_stage(self, stage_num: int, evidence: List[str]):
        self.current_stage_num = stage_num
        self.current_stage_evidence = evidence

    # ------------------------------------------------------------------
    # SUGGEST-06 : reset_cognitive_state 강화
    def reset_cognitive_state(self):
        """Reset but preserve critical information + POST-RESET BRIEFING"""
        self.conversation_history = []
        self.reset_count += 1
        self.student_error_tracker.clear()

        # --- 기본 프롬프트 복원 ---
        self.system_prompt = self.base_system_prompt
        if self.injected_constants:
            self.system_prompt += "\n\n" + self.injected_constants

        # --- confirmed_logic 주입 ---
        if self.confirmed_logic:
            confirmed_str = "\n\nCONFIRMED LOGICAL CONCLUSIONS (DO NOT QUESTION):\n"
            confirmed_str += "=" * 70 + "\n"
            for idx, node in enumerate(self.confirmed_logic, 1):
                confirmed_str += f"{idx}. {node.get('conclusion', 'N/A')}\n"
                confirmed_str += f"   Evidence: {node.get('evidence', 'N/A')}\n"
                confirmed_str += f"   Established in Session: {node.get('session', 'N/A')}\n\n"
            self.system_prompt += confirmed_str

        # --- SUGGEST-06 : current_stage_evidence 주입 ---
        if self.current_stage_evidence:
            stage_str = (
                f"\n\n📘 POST-RESET BRIEFING – Current Stage {self.current_stage_num} Evidence:\n"
                "The following evidence is NOW UNLOCKED and available for this stage.\n"
                "Use this context to evaluate professors' claims:\n"
            )
            stage_str += "\n".join(f"  • {ev}" for ev in self.current_stage_evidence)
            stage_str += "\n\nMaintain full strictness – reset does NOT mean leniency.\n"
            self.system_prompt += stage_str

        print(f"  ⟳ {self.name} reset (constants + confirmed_logic + stage_evidence preserved, "
              f"reset #{self.reset_count})")

    # ------------------------------------------------------------------
    # SUGGEST-02 : verify_statements에 개념 침투 체크 포함
    def verify_statements(self, professors_responses: List[str],
                          student_question: str,
                          session_num: int,
                          fixed_constants: Dict,
                          current_stage: int = 1,
                          current_stage_evidence: List[str] = None) -> Dict:

        constants_check = ""
        if fixed_constants:
            constants_check = "\n\nFIXED CONSTANTS ENFORCEMENT (ZERO TOLERANCE):\n"
            for key, value in fixed_constants.items():
                constants_check += f"- {key}: {value} (EXACT, no approximations)\n"
            constants_check += "\nANY use of '~', 'about', 'approximately' is CRITICAL error.\n"

        # SUGGEST-02 : 개념 침투 체크 블록
        concept_check_block = ""
        era_concepts = ProfessorAgent.ERA_CONCEPT_RESTRICTIONS.get(current_stage, [])
        if era_concepts:
            concept_check_block = (
                "\n\n⚠️ ERA-CONCEPT ANACHRONISM CHECK:\n"
                "The following CONCEPTS did not exist in Stage " + str(current_stage) + ".\n"
                "Flag ANY professor response that uses these concepts — "
                "even indirectly or without the exact forbidden word:\n"
                + "\n".join(f"  - {c}" for c in era_concepts) + "\n"
                "Mark such violations as type: \"anachronistic_concept\" with severity \"high\".\n"
            )

        all_statements = "\n\n---\n\n".join([
            f"Professor {i+1}:\n{resp}"
            for i, resp in enumerate(professors_responses)
        ])

        prompt = f"""{constants_check}
{concept_check_block}

SESSION {session_num} VERIFICATION:

STUDENT QUESTION:
{student_question}

PROFESSORS' RESPONSES:
{all_statements}

Verify each professor's statements. For EACH hallucination found, provide:
1. Professor index (0, 1, 2, or 3)
2. Exact statement with hallucination
3. Type of hallucination
4. Correct information
5. Severity level

Respond in JSON format:
{{
    "professor_hallucinations": [
        {{
            "professor_index": 0,
            "statement": "exact quote",
            "type": "factual_error | anachronistic_vocabulary | anachronistic_concept | approximation | logical_fallacy | contradiction",
            "correct_info": "correct version",
            "severity": "critical | high | medium | low"
        }}
    ],
    "student_errors_missed_by_professors": [
        {{
            "statement": "student's error",
            "why_missed": "explanation"
        }}
    ]
}}

If no hallucinations found, return empty arrays.
"""
        response = self._call_api(prompt, temperature=0.3)

        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response
            result = json.loads(json_str.strip())

            for err in result.get('student_errors_missed_by_professors', []):
                sig = err['statement'][:50]
                self.student_error_tracker[sig] += 1

            return result

        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parse error in {self.name}: {e}")
            print(f"      Raw response (first 200 chars): {response[:200]}")
            return {
                "professor_hallucinations": [],
                "student_errors_missed_by_professors": [],
                "parse_error": str(e)
            }
        except Exception as e:
            print(f"  ⚠️  Unexpected error in {self.name}: {e}")
            return {
                "professor_hallucinations": [],
                "student_errors_missed_by_professors": []
            }


# ===========================================================================
# RecorderAgent
# ===========================================================================
class RecorderAgent(PersonaAgent):
    """
    Records the entire debate for dataset creation.

    SUGGEST-04 : tiktoken 기반 토큰 수 계산
    """

    def __init__(self, name: str, client):
        system_prompt = """You are the DataRecorder, responsible for creating high-quality training data.

YOUR MISSION - CAUSAL CHAIN PRESERVATION (HIGHEST PRIORITY):
Your PRIMARY goal is to preserve the COMPLETE causal reasoning chain, not just outcomes.

PRIORITY ORDER (never deviate):
1. **Preserve all rebuttal-counter-rebuttal chains** (HIGHEST)
2. Document evidence used in each step
3. Record acknowledgments (but never at the expense of process)

CRITICAL RULES:
- NEVER summarize intermediate reasoning steps
- NEVER skip the "how we got from A to B" explanation
- The reasoning PATH is more valuable than the conclusion
- When student accepts a point, record BOTH the final acceptance AND the preceding argument chain

DATA QUALITY STANDARDS:
- Each exchange must show: Challenge → Evidence → Counter-argument → Resolution
- If a conclusion emerges, show the FULL logical path that led to it
- Brevity is NOT a virtue if it sacrifices reasoning completeness

TOKEN MANAGEMENT:
- Store exchanges in chunks to prevent context overflow
- Each chunk must be independently coherent
"""
        super().__init__(name, "Recorder", client, system_prompt)
        self.records: List[Dict] = []
        self.session_chunks: List[Dict] = []
        self.current_chunk_size = 0
        self.max_chunk_tokens = 15000

    def record_exchange(self, session_num: int, exchange_num: int,
                        student_question: str, professors_responses: List[str],
                        referee_results: List[Dict], context: str,
                        redundancy_status: str = "progressive") -> Dict:
        """Record a single exchange with full causal chain."""

        # SUGGEST-04 : tiktoken 기반 토큰 수 계산
        raw_text = student_question + "".join(professors_responses)
        estimated_tokens = count_tokens(raw_text)

        if self.current_chunk_size + estimated_tokens > self.max_chunk_tokens:
            print(f"  💾 Recorder: Chunk boundary reached ({self.current_chunk_size} tokens). "
                  f"Saving current chunk.")
            self.current_chunk_size = 0

        record = {
            "session": session_num,
            "exchange": exchange_num,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "student_challenge": student_question,
            "professor_responses": professors_responses,
            "referee_verification": referee_results,
            "estimated_tokens": estimated_tokens,
            "redundancy_assessment": {"status": redundancy_status}
        }

        self.records.append(record)
        self.session_chunks.append(record)
        self.current_chunk_size += estimated_tokens
        return record

    # ------------------------------------------------------------------
    def get_complete_dataset(self) -> List[Dict]:
        """Return all records including redundant ones."""
        return self.records

    def get_progressive_dataset(self) -> List[Dict]:
        """Return only non-redundant records."""
        return [r for r in self.records
                if r.get('redundancy_assessment', {}).get('status') != 'redundant']

    # ------------------------------------------------------------------
    def generate_sft_data(self) -> List[Dict]:
        sft_data = []
        for record in self.records:
            prompt = f"Context: {record['context']}\n\nStudent Question/Challenge:\n{record['student_challenge']}\n"
            response = "\n\n".join([
                f"Professor {i+1} Response:\n{resp}"
                for i, resp in enumerate(record['professor_responses'])
            ])
            sft_data.append({
                "prompt": prompt,
                "completion": response,
                "metadata": {
                    "session": record['session'],
                    "exchange": record['exchange'],
                    "has_hallucinations": any(
                        len(ref.get('professor_hallucinations', [])) > 0
                        for ref in record['referee_verification']
                    )
                }
            })
        return sft_data


# ===========================================================================
# ValidationSpecialist
# ===========================================================================
# ============================================================================
# CRITICAL: ValidationSpecialist 역할 격리
# 
# 이 페르소나는 토론 과정에 절대 개입하지 않습니다!
# 
# 허용되는 역할:
#   - Shadow Monitoring: 심판들의 논쟁을 기록만 함
#   - 사후 품질 감사: 모든 토론 종료 후 데이터 품질 평가
#   - 품질 표기: 심판 간 이견 미해결 시 "quality: low" 표기
# 
# 금지되는 역할:
#   - 실시간 개입: 토론 중 발언 금지
#   - 정답 판결: 심판 충돌 시 결론 내리기 금지
#   - 심판 영향: 심판의 독립성에 영향 금지
# ============================================================================
class ValidationSpecialist(PersonaAgent):
    """
    Final quality auditor.

    C-01: resolve_deadlock() 삭제됨 — 토론 중 개입 불가.
    심판 충돌은 교수 증거 제공 또는 Force-Proceed(SUGGEST-01)로만 해결됨.
    """

    def __init__(self, name: str, client):
        system_prompt = """You are the Quality Validator, conducting final audit of generated data.

YOUR MISSION:
- Assess overall data quality and consistency
- Identify any remaining logical gaps or inconsistencies
- Evaluate the pedagogical value of exchanges
- Provide recommendations for improvement
- ⭐ When called for DEADLOCK RESOLUTION: make a FINAL BINDING decision.
  You must NEVER return "undecided". Choose accept or reject based on available evidence.

QUALITY METRICS TO EVALUATE:
1. Logical coherence across all sessions
2. Consistency of facts and constants used
3. Depth of reasoning demonstrated
4. Effectiveness of skeptical challenges
5. Quality of evidence integration

OUTPUT FORMAT:
Provide structured assessment with:
- Overall quality score (0-100)
- Specific strengths identified
- Areas needing improvement
- Recommendations for future simulations
"""
        super().__init__(name, "Validator", client, system_prompt)

    # ------------------------------------------------------------------
    # C-01: resolve_deadlock 완전 삭제.
    # ValidationSpecialist는 토론 중 절대 개입하지 않음.
    # 심판 충돌 해결 경로:
    #   1) 교수가 추가 증거(3건 이상)를 제공 → hallucination 해제
    #   2) 교수 증거 부족 → deadlock_count += 1
    #   3) deadlock_count >= 2 → Force-Proceed (SUGGEST-01) → 세션종료
    # ------------------------------------------------------------------

    def audit_simulation(self, all_records: List[Dict],
                         hallucination_summary: Dict) -> Dict:
        summary = (
            f"SIMULATION SUMMARY:\n"
            f"Total Sessions: {len(set(r['session'] for r in all_records))}\n"
            f"Total Exchanges: {len(all_records)}\n"
            f"Total Hallucinations: {hallucination_summary.get('total', 0)}\n"
            f"Hallucination Rate: {hallucination_summary.get('rate', 0):.2%}\n\n"
            "Sample exchanges provided for review…\n"
        )

        sample_records = all_records[:3] + all_records[-3:]
        for rec in sample_records:
            summary += (
                f"\nSession {rec['session']}, Exchange {rec['exchange']}:\n"
                f"Student: {rec['student_challenge'][:200]}…\n"
                f"Professors: {len(rec['professor_responses'])} responses\n"
            )

        response = self._call_api(summary + "\nPlease provide a comprehensive quality assessment.\n",
                                  temperature=0.5)
        return {
            "audit_report": response,
            "timestamp": datetime.now().isoformat(),
            "hallucination_summary": hallucination_summary
        }


# ===========================================================================
# ProvenFactSystem – 메인 오케스트라테이터
# ===========================================================================
class ProvenFactSystem:
    """
    Main system orchestrating the debate simulation.

    SUGGEST-01 : Force-Proceed 플래그 (deadlock_count 추적)
    BUG-D      : conflict 중간 턴에서도 record_exchange 실행
    BUG-E      : hallucination에 session 필드 추가
    """

    def __init__(self, api_provider: str = "anthropic",
                 api_key: Optional[str] = None,
                 num_professors: int = 4,
                 num_referees: int = 2):

        # ── 유효성 체크 ──────────────────────────────────────────────
        if not 2 <= num_referees <= 3:
            raise ValueError("Number of referees must be 2 or 3")

        # GROK-C1: API 키 명시적 체크
        if api_key is None:
            api_key = os.getenv(f"{api_provider.upper()}_API_KEY")

        if not api_key:
            print("=" * 70)
            print(f"  ❌ ERROR: {api_provider.upper()}_API_KEY Not Found")
            print("=" * 70)
            print()
            print("  Please set your API key:")
            print()
            print(f"    export {api_provider.upper()}_API_KEY='your-key-here'")
            print()
            print("  Or pass it directly:")
            print(f"    system = ProvenFactSystem(api_key='your-key')")
            print()
            print("=" * 70)
            raise ValueError(f"{api_provider.upper()}_API_KEY not found in environment")

        # ── API 클라이언트 초기화 ─────────────────────────────────────
        if api_provider == "anthropic":
            if not _ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "anthropic package is not installed.\n"
                    "  Install it with:  pip install anthropic"
                )
            self.client = anthropic.Anthropic(api_key=api_key)
        elif api_provider == "openai":
            if not _OPENAI_AVAILABLE:
                raise ImportError(
                    "openai package is not installed.\n"
                    "  Install it with:  pip install openai"
                )
            self.client = openai.OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {api_provider}")

        self.api_provider = api_provider
        self.num_professors = num_professors
        self.num_referees = num_referees

        self.professors: List[ProfessorAgent] = []
        self.student: Optional[StudentAgent] = None
        self.referees: List[RefereeAgent] = []
        self.recorder: Optional[RecorderAgent] = None
        self.validator: Optional[ValidationSpecialist] = None

        self.fixed_constants: Dict = {}
        self.confirmed_logic: List[Dict] = []   # 시스템 전체 확정 논리 저장소

    # ------------------------------------------------------------------
    def _create_personas(self, topic: str, proven_fact: str):
        specialties = [
            "Physics and Astronomy",
            "Mathematics and Geometry",
            "History and Philosophy of Science",
            "Experimental Methods and Observation"
        ]
        self.professors = [
            ProfessorAgent(f"Prof. {chr(65+i)}", specialties[i], self.client, current_stage=1)
            for i in range(min(self.num_professors, len(specialties)))
        ]
        self.student = StudentAgent("Alex", self.client, skepticism_level="ultra-high")

        referee_schedules = generate_referee_schedules(self.num_referees, max_sessions=100)
        self.referees = [
            RefereeAgent(f"Referee_{i+1}", self.client,
                         reset_schedule=referee_schedules[i],
                         strictness="high")
            for i in range(self.num_referees)
        ]

        # BUG-B 수정 : 올바른 주기 표시
        print("✅ Referee Reset Schedules (v1.1.0):")
        if self.num_referees == 2:
            labels = ["5n (5,10,15…)", "5n-3 (2,7,12…)"]
        else:
            labels = ["7n (7,14,21…)", "7n-3 (4,11,18…)", "7n-5 (2,9,16…)"]
        for i, sched in enumerate(referee_schedules):
            print(f"   Referee {i+1}: {labels[i]}  →  first 6: {sched[:6]}")

        self.recorder = RecorderAgent("DataRecorder", self.client)
        self.validator = ValidationSpecialist("QualityValidator", self.client)

        print(f"✅ Created {len(self.professors)} professors, 1 student, "
              f"{len(self.referees)} referees, 1 recorder, 1 validator")

    # ------------------------------------------------------------------
    def _determine_stage_boundaries(self, total_sessions: int, num_stages: int = 4) -> List[int]:
        sessions_per_stage = total_sessions // num_stages
        remainder = total_sessions % num_stages
        boundaries, current = [], 0
        for i in range(num_stages):
            current += sessions_per_stage + (1 if i < remainder else 0)
            boundaries.append(current)
        return boundaries

    def _get_current_stage(self, session_num: int, boundaries: List[int]) -> int:
        for stage_idx, boundary in enumerate(boundaries, 1):
            if session_num <= boundary:
                return stage_idx
        return len(boundaries)

    def _format_constants_string(self) -> str:
        if not self.fixed_constants:
            return ""
        s = "\nFIXED PHYSICAL CONSTANTS (use EXACT values):\n" + "=" * 70 + "\n"
        for key, value in self.fixed_constants.items():
            s += f"- {key}: {value}\n"
        s += ("\nCRITICAL RULES:\n"
              "- Use these EXACT values, no approximations\n"
              "- Do NOT use '~', 'approximately', 'about', or 'roughly'\n"
              "- Any deviation is considered a hallucination\n"
              + "=" * 70 + "\n")
        return s

    # ------------------------------------------------------------------
    def _detect_referee_conflict(self, all_results: List[Dict]) -> Tuple[bool, List[Dict]]:
        if len(all_results) < 2:
            return False, []

        hallucination_map: Dict[str, List] = defaultdict(list)
        for ref_idx, result in enumerate(all_results):
            for hall in result.get('professor_hallucinations', []):
                prof_idx = hall.get('professor_index', -1)
                stmt_sig = f"{prof_idx}:{hall.get('statement', '')[:50]}"
                hallucination_map[stmt_sig].append({
                    'referee_idx': ref_idx,
                    'referee_name': self.referees[ref_idx].name,
                    'hallucination': hall
                })

        conflicts = []
        for stmt_sig, detections in hallucination_map.items():
            if 0 < len(detections) < len(all_results):
                conflicts.append({
                    'statement_signature': stmt_sig,
                    'flagged_by': detections,
                    'total_referees': len(all_results)
                })
        return len(conflicts) > 0, conflicts

    # ------------------------------------------------------------------
    # SUGGEST-01 + BUG-F 연동 : conflict 해결 시 ValidationSpecialist 활용
    def _resolve_referee_conflict(self, conflicts: List[Dict],
                                  professors: List[ProfessorAgent],
                                  fixed_constants: Dict,
                                  session_num: int,
                                  deadlock_count: int) -> Tuple[List[Dict], int]:
        """
        Returns: (resolved_hallucinations, updated_deadlock_count)

        SUGGEST-01 Flow:
          deadlock_count < 2  → professor defense → (resolve or increment deadlock_count)
          deadlock_count >= 2 → Force-Proceed: 교수 판정승, 로그만 남기고 진행
        """
        resolved_hallucinations: List[Dict] = []

        for conflict in conflicts:
            print(f"\n  ⚖️  REFEREE CONFLICT DETECTED:")
            print(f"      Statement: {conflict['statement_signature'][:60]}…")
            print(f"      Flagged by {len(conflict['flagged_by'])}/{conflict['total_referees']} referees")

            # ---- SUGGEST-01 : Force-Proceed 체크 ----
            if deadlock_count >= 2:
                print(f"      🚩 FORCE-PROCEED activated (deadlock_count={deadlock_count}). "
                      f"교수 판정승 – 할루시네이션 플래그 해제, 다음 논리로 진행.")
                # 교수 판정승 → hallucination을 resolved 목록에 넣지 않음
                continue

            primary_detection = conflict['flagged_by'][0]
            hall = primary_detection['hallucination']
            # BUG-E : session 필드 추가
            hall['session'] = session_num

            prof_idx = hall.get('professor_index', -1)
            if prof_idx < 0 or prof_idx >= len(professors):
                print(f"      ⚠️ Invalid professor index, skipping")
                continue

            professor = professors[prof_idx]
            print(f"      → Asking {professor.name} to provide evidence…")

            defense = professor.defend_against_referee(
                challenged_statement=hall.get('statement', ''),
                referee_reasoning=hall.get('correct_info', ''),
                fixed_constants=fixed_constants
            )

            if defense.get('acknowledges_error', False):
                print(f"      ✓ {professor.name} acknowledges error")
                resolved_hallucinations.append(hall)
            else:
                num_sources = len(defense.get('sources', []))
                print(f"      → {professor.name} defends with {num_sources} sources")

                if num_sources >= 3:
                    print(f"      ✓ Strong evidence – hallucination flag removed")
                    # hallucination 해제 → 목록에 추가하지 않음
                else:
                    # 소스 부족 + ValidationSpecialist 개입 금지 →
                    # hallucination을 유지하고 deadlock_count 증가
                    print(f"      ⚖️  Insufficient sources ({num_sources}/3). "
                          f"Flagging hallucination, incrementing deadlock count.")
                    hall['professor_defense_weak'] = True
                    hall['defense_sources_count'] = num_sources
                    resolved_hallucinations.append(hall)
                    deadlock_count += 1

        return resolved_hallucinations, deadlock_count

    # ------------------------------------------------------------------
    def _severity_score(self, hallucination: Dict) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(
            hallucination.get('severity', 'low'), 1)

    def _detect_loop(self, recent_topics: List[str], window: int = 3) -> bool:
        if len(recent_topics) < window:
            return False
        all_kw: set = set()
        for topic in recent_topics[-window:]:
            kw = set(topic.lower().split())
            if len(all_kw.intersection(kw)) > 3:
                return True
            all_kw.update(kw)
        return False

    # ------------------------------------------------------------------
    # MAIN SIMULATION LOOP
    def run_learning_simulation(self,
                                proven_fact: str,
                                topic: str,
                                evidence_stages: List[List[str]],
                                fixed_constants: Dict = None,
                                total_sessions: int = 12,
                                max_turns_per_session: int = 5,
                                output_file: str = "results.json",
                                verbose: bool = False) -> Dict:

        print(f"\n{'=' * 70}")
        print(f"  PROVEN FACT-BASED LEARNING SIMULATION  v1.4.0")
        print(f"{'=' * 70}")
        print(f"  Topic    : {topic}")
        print(f"  Sessions : {total_sessions}")
        print(f"  Profs    : {self.num_professors}  |  Referees: {self.num_referees}")
        print(f"{'=' * 70}\n")

        self.fixed_constants = fixed_constants or {}
        self._create_personas(topic, proven_fact)

        constants_str = self._format_constants_string()
        if constants_str:
            for prof in self.professors:
                prof.inject_constants(constants_str)
            for ref in self.referees:
                ref.inject_constants(constants_str)

        stage_boundaries = self._determine_stage_boundaries(total_sessions, len(evidence_stages))
        print(f"📊 Evidence Stage Boundaries: {stage_boundaries}\n")

        all_hallucinations: List[Dict] = []
        session_topics: List[str] = []
        self.confirmed_logic = []
        # ── C-02: pending_logic 스테이징 + consecutive_clean_count ──
        # 승격 규칙 (연속 2회 clean 필수):
        #   clean 세션  → count += 1;  현재 논리를 pending으로 저장
        #               → count >= 2 이면 직전 pending을 confirmed로 승격
        #   hallucination 세션 → count = 0; pending 폐기
        # 시뮬레이션 종료 시 남은 pending은 confirmed로 승격 (마지막 세션 보호)
        pending_logic: Optional[Dict] = None
        self.consecutive_clean_count = 0

        # ── SESSION 루프 ──────────────────────────────────────────────
        for session_num in range(1, total_sessions + 1):
            print(f"\n{'─' * 70}")
            print(f"SESSION {session_num}/{total_sessions}")
            print(f"{'─' * 70}")

            current_stage = self._get_current_stage(session_num, stage_boundaries)
            available_evidence = evidence_stages[current_stage - 1]
            print(f"📍 Evidence Stage: {current_stage}/4  |  Evidence items: {len(available_evidence)}")

            # --- stage transition ---
            if session_num > 1:
                prev_stage = self._get_current_stage(session_num - 1, stage_boundaries)
                if current_stage != prev_stage:
                    print(f"\n🔄 STAGE TRANSITION: {prev_stage} → {current_stage}")
                    for prof in self.professors:
                        prof.update_stage(current_stage)

            # --- referee reset + SUGGEST-06 stage 증거 업데이트 ---
            for referee in self.referees:
                referee.update_current_stage(current_stage, available_evidence)
                if session_num in referee.reset_schedule:
                    referee.reset_cognitive_state()

            # --- SUGGEST-03 : student에게 confirmed_logic 전달 ---
            if self.confirmed_logic:
                self.student.update_confirmed_logic(self.confirmed_logic)

            context = f"Topic: {topic}\nProven Fact: {proven_fact}\nCurrent Stage: {current_stage}"

            # ── TURN 루프 ────────────────────────────────────────────
            turn_count = 0
            session_complete = False
            session_hallucinations: List[Dict] = []
            deadlock_count = 0   # SUGGEST-01 : 세션 당 교착 횟수 추적
            professor_responses: List[str] = []   # 이전 턴 교수 응답 (학생에게 전달용)

            while not session_complete and turn_count < max_turns_per_session:
                turn_count += 1
                print(f"\n  Turn {turn_count}:")

                if self._detect_loop(session_topics):
                    print(f"  ⚠️  Loop detected – forcing new angle…")
                    context += "\n[Force new angle – avoid repetition]"

                # --- Student question ---
                student_errors = [
                    h['statement'] for h in session_hallucinations
                    if not h.get('professors_caught', True)
                ]
                # Turn 1: 교수 응답 아직 없음 → context만 전달
                # Turn 2+: 이전 턴 교수 응답을 학생에게 전달하여 토론 연속성 유지
                prev_prof_text = ""
                if turn_count > 1 and professor_responses:
                    prev_prof_text = "\n\n".join(
                        f"Professor {i+1}:\n{resp}"
                        for i, resp in enumerate(professor_responses)
                    )
                student_question = self.student.ask_question(
                    professors_explanation=prev_prof_text,
                    context=context,
                    previous_errors=student_errors or None,
                    confirmed_logic=self.confirmed_logic   # SUGGEST-03
                )
                if verbose:
                    print(f"\n  🎓 Student: {student_question[:200]}…")

                session_topics.append(' '.join(student_question.split()[:10]))

                # --- Professor responses (rotated order) ---
                order = list(range(len(self.professors)))
                order = order[turn_count % len(order):] + order[:turn_count % len(order)]

                consistency_reminder = (
                    "⚠️ CONSISTENCY CHECK:\n"
                    "Review your previous arguments to ensure you're not contradicting established points.\n"
                    "Build upon, don't undermine, previous reasoning.\n"
                ) if self.professors[0].previous_arguments else ""

                professor_responses = []   # 이번 턴 교수 응답 초기화
                for idx in order:
                    prof = self.professors[idx]
                    resp = prof.teach(
                        student_question=student_question,
                        context=context,
                        available_evidence=available_evidence,
                        consistency_reminder=consistency_reminder
                    )
                    professor_responses.append(resp)
                    if verbose:
                        print(f"\n  📚 {prof.name}: {resp[:200]}…")

                # --- Referee verification ---
                all_referee_results: List[Dict] = []
                for referee in self.referees:
                    result = referee.verify_statements(
                        professors_responses=professor_responses,
                        student_question=student_question,
                        session_num=session_num,
                        fixed_constants=self.fixed_constants,
                        current_stage=current_stage,                    # SUGGEST-02
                        current_stage_evidence=available_evidence       # SUGGEST-02
                    )
                    all_referee_results.append(result)

                # --- Conflict detection & resolution ---
                has_conflict, conflicts = self._detect_referee_conflict(all_referee_results)

                # BUG-D : record_exchange는 항상 실행 (continue 전에)
                self.recorder.record_exchange(
                    session_num=session_num,
                    exchange_num=turn_count,
                    student_question=student_question,
                    professors_responses=professor_responses,
                    referee_results=all_referee_results,
                    context=context
                )

                if has_conflict:
                    print(f"\n  ⚖️  REFEREE CONFLICT: {len(conflicts)} disagreement(s)")

                    resolved, deadlock_count = self._resolve_referee_conflict(
                        conflicts=conflicts,
                        professors=self.professors,
                        fixed_constants=self.fixed_constants,
                        session_num=session_num,
                        deadlock_count=deadlock_count
                    )
                    session_hallucinations.extend(resolved)

                    # SUGGEST-01 : Force-Proceed 후 세션 종료
                    if deadlock_count >= 2:
                        print(f"  🚩 FORCE-PROCEED: 교수 판정승으로 세션 종료. 다음 논리로 진행.")
                        session_complete = True
                    elif turn_count >= max_turns_per_session:
                        print(f"  🛑 Max turns reached after conflict resolution")
                        session_complete = True
                    # else: continue to next turn
                else:
                    # 충돌 없음 → 정상 종료
                    for result in all_referee_results:
                        for h in result.get('professor_hallucinations', []):
                            h['session'] = session_num   # BUG-E
                            session_hallucinations.append(h)
                    session_complete = True

            # ── SESSION 종료 정리 ─────────────────────────────────────
            if session_hallucinations:
                print(f"\n  ⚠️  Session {session_num}: {len(session_hallucinations)} hallucination(s)")
                all_hallucinations.extend(session_hallucinations)
                # C-02: 할루시네이션 발견 → 카운터 리셋 + pending 폐기
                self.consecutive_clean_count = 0
                if pending_logic is not None:
                    print(f"  🔒 Pending logic from Session {pending_logic['session']} "
                          f"discarded (hallucination detected → count reset to 0)")
                    pending_logic = None
            else:
                print(f"\n  ✅ Session {session_num}: Clean (no hallucinations)")

                # C-02: 연속 clean 카운터 증가
                self.consecutive_clean_count += 1
                print(f"  📊 consecutive_clean_count = {self.consecutive_clean_count}")

                # 카운터 >= 2 이고 직전 pending이 있으면 → confirmed로 승격
                if self.consecutive_clean_count >= 2 and pending_logic is not None:
                    self.confirmed_logic.append(pending_logic)
                    for referee in self.referees:
                        referee.add_confirmed_logic(pending_logic)
                    print(f"  ✅ Logic from Session {pending_logic['session']} "
                          f"promoted to confirmed (consecutive_clean_count={self.consecutive_clean_count} >= 2)")

                # 현재 세션의 논리 → pending으로 저장 (아직 승격되지 않음)
                pending_logic = {
                    "conclusion": (
                        f"Session {session_num} established valid reasoning about "
                        f"{topic} using Stage {current_stage} evidence"
                    ),
                    "evidence": available_evidence[:3],
                    "session": session_num
                }
                print(f"  ⏳ Logic from Session {session_num} staged as pending "
                      f"(awaiting next-session confirmation)")

            if turn_count >= max_turns_per_session and not session_complete:
                print(f"  ⏱️  Session force-completed after {turn_count} turns")

        # ── LOOP 종료 후: 마지막 pending이 남아있으면 confirmed로 승격 ──
        if pending_logic is not None:
            self.confirmed_logic.append(pending_logic)
            for referee in self.referees:
                referee.add_confirmed_logic(pending_logic)
            print(f"  ✅ Final pending logic from Session {pending_logic['session']} "
                  f"promoted to confirmed (end-of-simulation)")

        # ── FINAL VALIDATION ──────────────────────────────────────────
        print(f"\n{'=' * 70}")
        print(f"  FINAL VALIDATION")
        print(f"{'=' * 70}\n")

        hallucination_summary = {
            "total": len(all_hallucinations),
            "by_severity": {
                sev: len([h for h in all_hallucinations if h.get('severity') == sev])
                for sev in ('critical', 'high', 'medium', 'low')
            },
            "rate": len(all_hallucinations) / max(1, total_sessions * max_turns_per_session)
        }

        final_audit = self.validator.audit_simulation(
            all_records=self.recorder.records,
            hallucination_summary=hallucination_summary
        )

        sft_data = self.recorder.generate_sft_data()

        results = {
            "metadata": {
                "topic": topic,
                "proven_fact": proven_fact,
                "total_sessions": total_sessions,
                "num_professors": self.num_professors,
                "num_referees": self.num_referees,
                "timestamp": datetime.now().isoformat(),
                "api_provider": self.api_provider,
                "version": "1.3.0"
            },
            "fixed_constants": self.fixed_constants,
            "stage_boundaries": stage_boundaries,
            "confirmed_logic": self.confirmed_logic,
            "pending_logic": pending_logic,   # C-02: 현재 스테이진 논리 (None 또는 Dict)
            "all_records": self.recorder.records,
            "hallucinations": all_hallucinations,
            "hallucination_summary": hallucination_summary,
            "final_audit": final_audit,
            "sft_data": sft_data
        }

        # --- Save ---
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        sft_file = output_file.replace('.json', '.jsonl')
        with open(sft_file, 'w', encoding='utf-8') as f:
            for item in sft_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        print(f"\n{'=' * 70}")
        print(f"  SIMULATION COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Hallucinations   : {hallucination_summary['total']} "
              f"(rate {hallucination_summary['rate']:.2%})")
        print(f"  SFT examples     : {len(sft_data)}")
        print(f"  Confirmed Logic  : {len(self.confirmed_logic)} nodes")
        print(f"  Results          : {output_file}")
        print(f"  SFT data         : {sft_file}")
        print(f"{'=' * 70}\n")

        return results


# ===========================================================================
# CLI entry point
# ===========================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description='Run Proven Fact-Based Algorithm v1.4.0')
    parser.add_argument('--api', choices=['anthropic', 'openai'], default='anthropic')
    parser.add_argument('--sessions', type=int, default=12)
    parser.add_argument('--referees', type=int, choices=[2, 3], default=2)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    system = ProvenFactSystem(api_provider=args.api, num_referees=args.referees)

    example_config = {
        "proven_fact": "The Earth is approximately spherical with a circumference of 40,075 km at the equator.",
        "topic": "The Spherical Shape of Earth",
        "fixed_constants": {
            "Earth_circumference_km": 40075,
            "Earth_diameter_km": 12742,
            "Greek_stadium_meters": 185
        },
        "evidence_stages": [
            ["Ships disappear hull-first over horizon"],
            ["Eratosthenes measured Earth's circumference using shadows"],
            ["Magellan's circumnavigation completed"],
            ["Satellite photos from space"]
        ]
    }

    system.run_learning_simulation(
        proven_fact=example_config["proven_fact"],
        topic=example_config["topic"],
        evidence_stages=example_config["evidence_stages"],
        fixed_constants=example_config["fixed_constants"],
        total_sessions=args.sessions,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
