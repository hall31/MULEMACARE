# MulemaCare Health AI Agents — 55 Specialist Prompts

## Overview

**health_ai_prompts.json** contains 55 clinical AI agent prompts structured across 11 medical specialties. Each prompt is calibrated for:

- **Persona**: Physician + 5+ years African medical practice experience
- **Languages**: Mixed FR/EN/Swahili support (code-switching for diaspora)
- **Guardrails**: Never diagnose; always hedge ("might be X but see doctor")
- **Red Flags**: Specialty-specific emergency indicators
- **Escalation**: Transmission triggers to Lisacare doctors
- **Output Format**: Structured ClinCard JSON

## Categories (11 × 5 = 55 Agents)

| # | Category | Agents |
|---|----------|--------|
| 1 | **Pediatrics** | Newborn (0-1m), Infant (1-12m), Toddler (1-3y), Child (4-12y), Adolescent (13-18y) |
| 2 | **General Practice** | Adult Triage, Elderly (60+), Preventive, Chronic Base, Post-Op |
| 3 | **Women's Health** | Pregnancy, Postpartum, Gynecology, Contraception, Fertility |
| 4 | **Infectious Diseases** | Malaria, Dengue, Cholera, COVID/RSV, Tuberculosis |
| 5 | **Chronic Diseases** | Diabetes, Hypertension, HIV, Asthma, Chronic Kidney Disease |
| 6 | **Mental Health** | Depression, Anxiety, Trauma/PTSD, Substance Abuse, Psychosis |
| 7 | **Orthopedic & Pain** | Fracture, Back Pain, Sports Injury, Arthritis, Herniated Disc |
| 8 | **Dermatology** | Rash, Bacterial Infection, Fungal/Parasitic, Allergic, Chronic Skin |
| 9 | **Cardiology** | Chest Pain, Palpitations, Syncope, Murmur, Edema/Heart Failure |
| 10 | **Gastroenterology** | Diarrhea, Vomiting, Peptic Ulcer, Acute Abdomen, Hepatitis |
| 11 | **Neurology** | Headache, Seizure, Stroke, Numbness, Dizziness/Vertigo |

## Agent Structure

Each agent contains:

```json
{
  "id": "peds_001_newborn",
  "name": "Newborn Care Specialist",
  "specialty": "Pediatrics - Newborn (0-1 month)",
  "languages": ["FR", "EN", "Swahili", "code-switch"],
  "persona": "Pediatrician with 5 years experience...",
  "prompt": "Tu es un pédiatre spécialisé...",
  "red_flags": ["Temperature >38.5°C", "Lethargy or decreased responsiveness", ...],
  "transmission_triggers": ["Neonatal fever", "Persistent poor feeding", ...],
  "output_format": "ClinCard"
}
```

### Key Fields

- **id**: Unique identifier (format: `specialty_number_condition`)
- **prompt**: Full clinical reasoning prompt with guardrails, red flags, and output instructions
- **red_flags**: Critical safety indicators (auto-escalate to Lisacare if present)
- **transmission_triggers**: Conditions requiring physician referral
- **output_format**: Always `ClinCard` (structured JSON with parsed symptoms, hypotheses, next steps)

## Integration with Claude API

### Example: Using Pediatric Newborn Agent

```python
import anthropic
import json

# Load prompts
with open("health_ai_prompts.json") as f:
    prompts_db = json.load(f)

# Find agent
agent = prompts_db["categories"][0]["agents"][0]  # peds_001_newborn

# Claude API call
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-opus-4",
    max_tokens=1024,
    system=agent["prompt"],
    messages=[
        {
            "role": "user",
            "content": "Mon bébé a une fièvre 38.6°C et pleure beaucoup. Il refuse le lait maternellement. C'est inquiétant?"
        }
    ]
)

# Parse ClinCard response
output = response.content[0].text
print(output)
```

### Response Format (ClinCard)

Expected output structure:

```json
{
  "symptoms_parsed": [
    "fever 38.6C",
    "excessive crying",
    "poor feeding"
  ],
  "hypotheses_ranked": [
    "neonatal infection (requires monitoring)",
    "feeding difficulty (likely)",
    "inadequate milk transfer (check latch)"
  ],
  "red_flags_present": {
    "fever >38.5C": true,
    "poor feeding >3 feedings": "assess"
  },
  "next_steps": [
    "assess feeding technique with mother",
    "monitor for signs of infection (skin warmth, lethargy)",
    "seek Lisacare doctor if fever continues >4 hours or new signs appear"
  ],
  "recommend_lisacare_doctor": false,
  "recommend_lisacare_doctor_reason": "Fever in neonates is concerning. Escalate immediately if: persistent fever >38.5°C, poor feeding >3 missed feedings, signs of sepsis."
}
```

## Red Flags & Escalation

### Automatic Escalation to Lisacare Doctor

If **any** of these conditions are met:

- **Pediatrics**: Fever >38.5°C (neonates), respiratory rate >60/min, signs of sepsis
- **General Practice**: Chest pain, stroke signs, severe trauma, sepsis
- **Women's Health**: Vaginal bleeding >spotting, pre-eclampsia signs, decreased fetal movement
- **Infectious Diseases**: Cerebral malaria, dengue hemorrhagic fever, cholera severe
- **Chronic Diseases**: DKA, HHS, hypertensive emergency, CD4 <50 (HIV)
- **Mental Health**: Suicidal ideation with plan, psychosis, severe substance withdrawal
- **Orthopedic**: Open fracture, neurovascular compromise, compartment syndrome
- **Dermatology**: Petechial rash (meningococcemia), anaphylaxis, facial edema
- **Cardiology**: STEMI pattern, hemodynamic arrhythmia, shock signs
- **Gastroenterology**: GI bleeding, perforation, cholera, severe dehydration
- **Neurology**: Meningitis (fever + neck stiffness), stroke (thunderclap or signs), status epilepticus

## Guardrails Applied to All 55 Agents

1. **Never diagnose directly**: "You have X" is forbidden. Always use "could be X but see doctor"
2. **Acknowledge uncertainty**: Medical reasoning is probabilistic; rank hypotheses by likelihood
3. **Language-aware**: Accept code-switched FR/EN/Swahili; respond in patient's language preference
4. **Cultural sensitivity**: 
   - Diaspora families have access barriers (lab tests, specialist visits)
   - Tailor recommendations to resource-limited settings
   - No assumptions about medication availability
5. **Safety first**: When in doubt, escalate to Lisacare doctor
6. **No invention**: Don't create fake statistics or cite non-existent studies

## Deployment

Place **health_ai_prompts.json** in:
```
/api/app/services/agents/
```

Load in FastAPI endpoint:

```python
# api/app/api/agents.py
from fastapi import APIRouter
import json

router = APIRouter(prefix="/agents", tags=["agents"])

with open("app/services/agents/health_ai_prompts.json") as f:
    HEALTH_AGENTS = json.load(f)

@router.post("/health-ai/{agent_id}")
async def call_health_agent(agent_id: str, user_message: str):
    agent = next(
        (a for cat in HEALTH_AGENTS["categories"] 
         for a in cat["agents"] if a["id"] == agent_id),
        None
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Call Claude API with agent["prompt"] as system message
    # Return ClinCard JSON
```

## Quality Assurance

- ✓ 55 agents (11 categories × 5 specialties)
- ✓ All guardrails applied (no direct diagnosis)
- ✓ Red flags indexed by category
- ✓ Transmission triggers defined
- ✓ ClinCard output format standardized
- ✓ FR/EN/Swahili language support
- ✓ African medical context (5+ years experience)

## Version

- **Version**: 1.0.0
- **Created**: 2026-08-30
- **Prompt Size**: ~500 chars per agent (optimized for Claude API token efficiency)
