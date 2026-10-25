"""The AI Act as code: fixed questions the LLM answers from the case, and the rules that decide on the answers.

Each question carries its legal test as a verbatim anchor inside one corpus heading; the passage is looked up at
runtime, so a corpus rebuild updates the text and a test fails if an anchor no longer matches exactly one passage.
"""

from typing import NamedTuple

from src import law
from src.citations import find_span


class Question(NamedTuple):
    id: str
    group: str  # A scope, B role, C prohibited, D Annex I, E Annex III, F Art 6(3), G Art 50, H GPAI
    text: str
    ref: str  # corpus heading the legal test sits under, e.g. "eu_ai_act/art-5"
    anchor: str  # verbatim phrase of the legal test inside that heading
    gating: bool = False  # unknown answer leaves the tier or role unclear


ACT, ANNEX_III = f"{law.ACT}/art-", f"{law.ACT}/anx-III"
Q = Question
QUESTIONS = [
    # A. Scope (Art 3(1), Art 2, AI system guidelines)
    Q("A1", "A", "Does the system infer from the input it receives how to generate outputs such as predictions, content, "
      "recommendations or decisions, rather than only executing rules written by people?", ACT + "3",
      "means a machine-based system that is designed to operate with varying levels of autonomy", gating=True),
    Q("A2", "A", "Is it only basic data processing: predefined rules, descriptive statistics, dashboards or visualisation, "
      "without learning, reasoning or modelling?", "guidelines_ai_system_definition/s-5.2",
      "Basic data processing system refers to a system that follows predefined, explicit instructions or operations"),
    Q("A3", "A", "Is the system placed on the market or put into service in the EU, used by a business located in the EU, "
      "or is its output used in the EU?", ACT + "2", "where the output produced by the AI system is used in the Union"),
    Q("A4", "A", "Is it used exclusively for military, defence or national security purposes?", ACT + "2",
      "used with or without modification exclusively for military, defence or national security purposes"),
    Q("A5", "A", "Is it developed and put into service for the sole purpose of scientific research and development?",
      ACT + "2", "specifically developed and put into service for the sole purpose of scientific research and development"),
    Q("A6", "A", "Is the activity only research, testing or development before the system is placed on the market or put "
      "into service (and not testing in real-world conditions)?", ACT + "2",
      "does not apply to any research, testing or development activity regarding AI systems or AI models prior to"),
    Q("A7", "A", "Is the user a private individual using it for a purely personal, non-professional activity?", ACT + "2",
      "natural persons using AI systems in the course of a purely personal non-professional activity"),
    Q("A8", "A", "Is the system released under a free and open-source licence?", ACT + "2",
      "does not apply to AI systems released under free and open-source licences"),
    # B. Role (Art 3(3), 3(4), Art 25, Art 27 deployer type)
    Q("B1", "B", "Does the business develop the system, or have it developed, and place it on the market or put it into "
      "service under its own name or trademark? Building or integrating a system, also on top of a third-party model, and "
      "offering or running it under its own name counts.", ACT + "3",
      "that develops an AI system or a general-purpose AI model or that has an AI system", gating=True),
    Q("B2", "B", "Does the business itself use the system under its own authority in its own professional activity? "
      "Developing, selling, licensing or hosting it for customers who use it is not use.", ACT + "3",
      "using an AI system under its authority except where the AI system is used in the course of a personal", gating=True),
    Q("B3", "B", "Does the business put its own name or trademark on a high-risk AI system that someone else already "
      "placed on the market or put into service?", ACT + "25",
      "they put their name or trademark on a high-risk AI system already placed on the market"),
    Q("B4", "B", "Does the business make a substantial modification to a high-risk AI system already on the market or in "
      "service?", ACT + "25", "they make a substantial modification to a high-risk AI system"),
    Q("B5", "B", "Does the business change the intended purpose of an AI system that was not high-risk (including a "
      "general-purpose AI system such as a chatbot) so that it becomes high-risk?", ACT + "25",
      "they modify the intended purpose of an AI system, including a general-purpose AI system"),
    Q("B6", "B", "Is the business a public authority or another body governed by public law (for example a ministry, "
      "municipality, agency, public school or hospital), or a private entity providing public services?",
      ACT + "27", "deployers that are bodies governed by public law, or are private entities providing public services"),
    # C. Prohibited practices (Art 5(1)) and their exceptions
    Q("C1", "C", "Does it use subliminal, purposefully manipulative or deceptive techniques that materially distort "
      "people's behaviour in a way that causes or is likely to cause significant harm?", ACT + "5",
      "deploys subliminal techniques beyond a person"),
    Q("C2", "C", "Does it exploit vulnerabilities due to age, disability or a specific social or economic situation to "
      "materially distort behaviour in a way that causes or is likely to cause significant harm?", ACT + "5",
      "exploits any of the vulnerabilities of a natural person or a specific group of persons due to their age"),
    Q("C3", "C", "Does it generate or manipulate realistic intimate or sexually explicit images, video or audio of an "
      "identifiable person without their explicit consent, as its purpose or without adequate safeguards against it?",
      ACT + "5", "generates or manipulates realistic images, videos, audio or similar material of an identifiable natural person"),
    Q("C4", "C", "Does it generate or manipulate child sexual abuse material?", ACT + "5",
      "within the meaning of Article 2, points (c) and (e), of Directive 2011/93/EU"),
    Q("C5", "C", "Does it score or classify people over time based on their social behaviour or personal characteristics, "
      "leading to unfavourable treatment in unrelated contexts or out of proportion to that behaviour?", ACT + "5",
      "for the evaluation or classification of natural persons or groups of persons over a certain period of time"),
    Q("C6", "C", "Does it assess or predict the risk that a person will commit a criminal offence based solely on "
      "profiling or on their personality traits and characteristics?", ACT + "5",
      "to assess or predict the risk of a natural person committing a criminal offence, based solely on the profiling"),
    Q("C7", "C", "Does it only support a human assessment of a person's involvement in a criminal activity that is "
      "already based on objective and verifiable facts?", ACT + "5",
      "this prohibition shall not apply to AI systems used to support the human assessment"),
    Q("C8", "C", "Does it create or expand facial recognition databases through untargeted scraping of facial images "
      "from the internet or CCTV footage?", ACT + "5", "untargeted scraping of facial images from the internet or CCTV footage"),
    Q("C9", "C", "Does it infer the emotions of people in the workplace or in education institutions?", ACT + "5",
      "to infer emotions of a natural person in the areas of workplace and education institutions"),
    Q("C10", "C", "Is that emotion inference intended for medical or safety reasons, such as protecting people's health "
      "or preventing accidents and incidents?", ACT + "5",
      "intended to be put in place or into the market for medical or safety reasons"),
    Q("C11", "C", "Does it categorise individual people from their biometric data to deduce their race, political "
      "opinions, trade union membership, religious or philosophical beliefs, sex life or sexual orientation?", ACT + "5",
      "categorise individually natural persons based on their biometric data to deduce or infer their race"),
    Q("C12", "C", "Is it only labelling or filtering lawfully acquired biometric datasets, or categorising biometric "
      "data in the area of law enforcement?", ACT + "5",
      "this prohibition does not cover any labelling or filtering of lawfully acquired biometric datasets"),
    Q("C13", "C", "Is it used for real-time remote biometric identification in publicly accessible spaces for law "
      "enforcement?", ACT + "5",
      "remote biometric identification systems in publicly accessible spaces for the purposes of law enforcement, unless"),
    Q("C14", "C", "Is that use strictly necessary for one of the listed objectives: searching for specific victims or "
      "missing persons, preventing a specific imminent threat to life or a terrorist attack, or locating a suspect of a "
      "serious offence listed in Annex II?", ACT + "5", "the targeted search for specific victims of abduction"),
    # D. Annex I route (Art 6(1), 6(1a)-(1c))
    Q("D1", "D", "Is the system a product, or a safety component of a product, covered by the EU legislation listed in "
      "Annex I (for example machinery, toys, lifts, radio equipment, medical devices, vehicles, aviation)?", ACT + "6",
      "the AI system is intended to be used as a safety component of a product, or the AI system is itself a product"),
    Q("D2", "D", "Must that product undergo a third-party conformity assessment under that legislation because of "
      "health or safety risks?", ACT + "6",
      "the AI system itself as a product, is required to undergo a third-party conformity assessment"),
    Q("D3", "D", "Is it used solely for non-safety aspects (user assistance, performance optimisation, efficiency, "
      "automation, convenience or quality control), with no danger to health or safety if it fails?", ACT + "6",
      "solely used for non-safety related aspects of user assistance"),
    # E. Annex III areas (Art 6(2)), one question per point
    Q("E1a", "E", "Is it a remote biometric identification system (not mere verification that a person is who they "
      "claim to be)?", ANNEX_III, "(a) remote biometric identification systems."),
    Q("E1b", "E", "Is it used for biometric categorisation by sensitive or protected attributes inferred from "
      "biometric data?", ANNEX_III, "AI systems intended to be used for biometric categorisation, according to sensitive"),
    Q("E1c", "E", "Is it used for emotion recognition?", ANNEX_III, "AI systems intended to be used for emotion recognition"),
    Q("E2", "E", "Is it a safety component in the management or operation of critical digital infrastructure, road "
      "traffic, or the supply of water, gas, heating or electricity?", ANNEX_III,
      "safety components in the management and operation of critical digital infrastructure"),
    Q("E3a", "E", "Does it determine access or admission to, or assign people to, educational or vocational training "
      "institutions?", ANNEX_III, "to determine access or admission or to assign natural persons to educational"),
    Q("E3b", "E", "Does it evaluate learning outcomes or steer students' learning?", ANNEX_III,
      "AI systems intended to be used to evaluate learning outcomes"),
    Q("E3c", "E", "Does it assess the level of education a person will receive or can access?", ANNEX_III,
      "assessing the appropriate level of education that an individual will receive"),
    Q("E3d", "E", "Does it monitor or detect prohibited behaviour of students during tests?", ANNEX_III,
      "monitoring and detecting prohibited behaviour of students during tests"),
    Q("E4a", "E", "Is it used to recruit or select people: targeted job ads, filtering applications, evaluating "
      "candidates?", ANNEX_III, "AI systems intended to be used for the recruitment or selection of natural persons"),
    Q("E4b", "E", "Does it make decisions on terms of work, promotion or termination, allocate tasks based on behaviour "
      "or personal traits, or monitor and evaluate workers' performance and behaviour?", ANNEX_III,
      "to make decisions affecting terms of work-related relationships"),
    Q("E5a", "E", "Is it used by or for public authorities to evaluate eligibility for public assistance benefits and "
      "services, or to grant, reduce, revoke or reclaim them?", ANNEX_III,
      "to evaluate the eligibility of natural persons for essential public assistance benefits and services"),
    Q("E5b", "E", "Does it evaluate people's creditworthiness or credit score (not merely detect financial fraud)?",
      ANNEX_III, "to evaluate the creditworthiness of natural persons or establish their credit score"),
    Q("E5c", "E", "Is it used for risk assessment and pricing of people for life or health insurance?", ANNEX_III,
      "risk assessment and pricing in relation to natural persons in the case of life and health insurance"),
    Q("E5d", "E", "Does it evaluate or classify emergency calls, dispatch or prioritise emergency services, or triage "
      "emergency healthcare patients?", ANNEX_III, "to evaluate and classify emergency calls by natural persons"),
    Q("E6a", "E", "Is it used by or for law enforcement to assess a person's risk of becoming a crime victim?", ANNEX_III,
      "to assess the risk of a natural person becoming the victim of criminal offences"),
    Q("E6b", "E", "Is it used by or for law enforcement as a polygraph or similar tool?", ANNEX_III,
      "in support of law enforcement authorities as polygraphs or similar tools"),
    Q("E6c", "E", "Is it used by or for law enforcement to evaluate the reliability of evidence?", ANNEX_III,
      "to evaluate the reliability of evidence in the course of the investigation or prosecution"),
    Q("E6d", "E", "Is it used by or for law enforcement to assess a person's risk of offending or re-offending, or their "
      "personality traits or past criminal behaviour?", ANNEX_III,
      "for assessing the risk of a natural person offending or re-offending"),
    Q("E6e", "E", "Is it used by or for law enforcement to profile people when detecting, investigating or prosecuting "
      "crimes?", ANNEX_III, "for the profiling of natural persons as referred to in Article 3(4) of Directive (EU) 2016/680 in the course"),
    Q("E7a", "E", "Is it used by or for migration, asylum or border authorities as a polygraph or similar tool?",
      ANNEX_III, "by or on behalf of competent public authorities or by Union institutions, bodies, offices or agencies as polygraphs"),
    Q("E7b", "E", "Is it used by or for those authorities to assess a security, irregular-migration or health risk posed "
      "by a person entering the EU?", ANNEX_III, "a risk of irregular migration, or a health risk"),
    Q("E7c", "E", "Is it used to examine applications for asylum, visas or residence permits?", ANNEX_III,
      "for the examination of applications for asylum, visa or residence permits"),
    Q("E7d", "E", "Is it used in migration, asylum or border control to detect, recognise or identify people (other "
      "than verifying travel documents)?", ANNEX_III, "for the purpose of detecting, recognising or identifying natural persons"),
    Q("E8a", "E", "Does it assist a judicial authority (or alternative dispute resolution) in researching and "
      "interpreting facts and law and applying the law?", ANNEX_III,
      "to assist a judicial authority in researching and interpreting facts and the law"),
    Q("E8b", "E", "Is it used to influence the outcome of an election or referendum or people's voting behaviour, with "
      "voters directly exposed to its output?", ANNEX_III, "for influencing the outcome of an election or referendum"),
    # F. Art 6(3) exception and profiling
    Q("F1", "F", "Does it only perform a narrow procedural task?", ACT + "6",
      "the AI system is intended to perform a narrow procedural task"),
    Q("F2", "F", "Does it only improve the result of a human activity that was already completed?", ACT + "6",
      "intended to improve the result of a previously completed human activity"),
    Q("F3", "F", "Does it only detect decision-making patterns or deviations, without replacing or influencing the "
      "completed human assessment without proper human review?", ACT + "6",
      "intended to detect decision-making patterns or deviations from prior decision-making patterns"),
    Q("F4", "F", "Does it only perform a preparatory task to an assessment for one of the Annex III uses?", ACT + "6",
      "intended to perform a preparatory task to an assessment"),
    Q("F5", "F", "Does it profile natural persons (automatically evaluate personal aspects such as performance, "
      "economic situation, health, preferences, behaviour or location)?", ACT + "6",
      "shall always be considered to be high-risk where the AI system performs profiling of natural persons"),
    # G. Transparency (Art 50)
    Q("G1", "G", "Does it interact directly with people, for example as a chatbot or voice assistant?", ACT + "50",
      "AI systems intended to interact directly with natural persons are designed and developed"),
    Q("G2", "G", "Does it generate synthetic audio, image, video or text content?", ACT + "50",
      "generating synthetic audio, image, video or text content"),
    Q("G3", "G", "Is it an emotion recognition or biometric categorisation system that people are exposed to?",
      ACT + "50", "Deployers of an emotion recognition system or a biometric categorisation system shall inform"),
    Q("G4", "G", "Does it generate or manipulate image, audio or video content that is a deep fake?", ACT + "50",
      "constituting a deep fake, shall disclose"),
    Q("G5", "G", "Does it generate or manipulate text published to inform the public on matters of public interest?",
      ACT + "50", "generates or manipulates text which is published with the purpose of informing the public"),
    # H. General-purpose AI (Art 3(63), 51, 53)
    Q("H1", "H", "Is the system built on a general-purpose AI model, such as a large language model or foundation model? "
      "Answer no when the documents describe the system's own model and it is not a general-purpose one.",
      ACT + "3", "means an AI model, including where such an AI model is trained with a large amount of data"),
    Q("H2", "H", "Does the business itself train, or place on the market, that general-purpose AI model?", ACT + "53",
      "draw up and keep up-to-date the technical documentation of the model"),
    Q("H3", "H", "Is that model a general-purpose AI model with systemic risk (high-impact capabilities, such as training "
      "compute above 10^25 FLOPs, or designated by the Commission)?", ACT + "51",
      "shall be classified as a general-purpose AI model with systemic risk if it meets any of the following conditions"),
]
BY_ID = {q.id: q for q in QUESTIONS}


TIERS = ["minimal_risk", "limited_risk", "high_risk", "prohibited"]  # ascending severity
_ART5 = [("C1", None), ("C2", None), ("C3", None), ("C4", None), ("C5", None), ("C6", "C7"), ("C8", None),
         ("C9", "C10"), ("C11", "C12"), ("C13", "C14")]  # (practice, its exception)
_EXCLUSIONS = ["A4", "A5", "A6"]  # Art 2(3), 2(6), 2(8); personal use (A7, Art 2(10)) only removes deployer duties


def classify(answers: dict[str, str]) -> dict:
    """Apply the Act to the answers ("yes" / "no" / "not_mentioned"; missing = not_mentioned). Pure.

    The tier is the most severe confirmed one. An unknown answer that could raise it sets `could_be` and becomes an
    open question; an unknown exception never lowers the tier (fail closed). Unknown AI-system status (A1) or EU link
    (A3) is assumed, as the case was uploaded as an AI use case, and asked: A1 then leaves ai_system unclear, confidence low.
    """
    path, open_questions, pending = [], [], []

    def ask(qid: str) -> str:
        a = answers.get(qid, "not_mentioned")
        path.append({"question": qid, "answer": a, "ref": BY_ID[qid].ref})
        if a == "not_mentioned" and qid not in open_questions:
            open_questions.append(qid)
        return a

    def unknown(qid: str, tier: str) -> None:  # unanswered; would lead to `tier`, asked only if above the final tier
        if answers.get(qid, "not_mentioned") == "not_mentioned":
            pending.append((qid, tier))

    def decision(tier: str, ai_system: str | None = None, exception: bool = False) -> dict:
        ai_system = ai_system or ("unclear" if a1 == "not_mentioned" else "yes")
        higher = [(q, t) for q, t in pending if tier in TIERS and TIERS.index(t) > TIERS.index(tier)]
        for q, _ in higher:
            ask(q)
        could_be = max((t for _, t in higher), key=TIERS.index, default=None)
        role = _role(answers, tier, ask if tier != "out_of_scope" else answers.get)
        gpai = {"yes": "yes", "no": "no"}.get(answers.get("H1"), "unclear")
        unsure = tier == "unclear" or could_be or ai_system == "unclear"
        confidence = "low" if unsure else "medium" if open_questions else "high"
        return {"ai_system": ai_system, "risk_tier": tier, "role": role, "gpai_involved": gpai, "confidence": confidence,
                "could_be": could_be, "annex_iii_exception": exception, "path": path, "open_questions": open_questions,
                "transparency": [q for q in ("G1", "G2", "G3", "G4", "G5") if answers.get(q) == "yes"]}

    # 1. AI system (Art 3(1), guidelines) and scope (Art 2)
    a1, a2 = ask("A1"), answers.get("A2", "not_mentioned")
    if a1 == "no" or a2 == "yes":
        if a2 == "yes":
            ask("A2")
        return decision("out_of_scope", ai_system="no")
    if ask("A3") == "no" or any(answers.get(q) == "yes" and ask(q) for q in _EXCLUSIONS):
        return decision("out_of_scope")

    # 2. Prohibited practices (Art 5): an unknown exception keeps the prohibition
    for practice, exception in _ART5:
        if answers.get(practice) == "yes":
            ask(practice)
            if exception is None or ask(exception) != "yes":
                return decision("prohibited")
    for practice, _ in _ART5:
        unknown(practice, "prohibited")

    # 3. High-risk via Annex I (Art 6(1), 6(1a)-(1b))
    d = {q: answers.get(q, "not_mentioned") for q in ("D1", "D2", "D3")}
    if d["D1"] == "yes" and d["D3"] != "yes":
        ask("D1")
        if d["D2"] == "yes":
            ask("D2")
            return decision("high_risk")
        unknown("D2", "high_risk")
    else:
        unknown("D1", "high_risk")

    # 4. High-risk via Annex III (Art 6(2)), unless an Art 6(3) condition holds and there is no profiling (Art 6(3)-(4))
    listed = [q.id for q in QUESTIONS if q.group == "E" and answers.get(q.id) == "yes"]
    if listed:
        for qid in listed:
            ask(qid)
        conditions = [q for q in ("F1", "F2", "F3", "F4") if answers.get(q) == "yes"]
        if not conditions or ask("F5") != "no":  # unknown profiling keeps it high-risk
            return decision("high_risk")
        for q in conditions:
            ask(q)
        exception = True
    else:
        exception = False
        for q in QUESTIONS:
            if q.group == "E":
                unknown(q.id, "high_risk")

    # 5. Transparency (Art 50), then minimal; open-source systems below that are excluded (Art 2(12))
    tier = "limited_risk" if any(answers.get(q) == "yes" and ask(q) for q in ("G1", "G2", "G3", "G4", "G5")) else "minimal_risk"
    if tier == "minimal_risk" and answers.get("A8") == "yes":
        ask("A8")
        return decision("out_of_scope")
    return decision(tier, exception=exception)


def _role(answers: dict[str, str], tier: str, ask) -> str:
    """Provider (Art 3(3), or Art 25(1) for high-risk systems), deployer (Art 3(4)), both, or unclear."""
    provider = ask("B1") == "yes" or (tier == "high_risk" and any(answers.get(q) == "yes" and ask(q) for q in ("B3", "B4", "B5")))
    deployer = ask("B2") == "yes"
    return "both" if provider and deployer else "provider" if provider else "deployer" if deployer else "unclear"


class Obligation(NamedTuple):
    id: str  # unique per row; the article is in ref
    requirement: str
    ref: str
    anchor: str  # verbatim from the passage, so it doubles as the quote of the code-written legal claim


O = Obligation
_PROVIDER_HIGH_RISK = [
    O("9", "Risk management system", ACT + "9", "A risk management system shall be established, implemented, documented and maintained"),
    O("10", "Data and data governance", ACT + "10", "shall be developed on the basis of training, validation and testing data sets that meet the quality criteria"),
    O("11", "Technical documentation", ACT + "11", "The technical documentation of a high-risk AI system shall be drawn up before that system is placed on the market"),
    O("12", "Record-keeping (logs)", ACT + "12", "High-risk AI systems shall technically allow for the automatic recording of events (logs)"),
    O("13", "Transparency and instructions for use", ACT + "13", "designed and developed in such a way as to ensure that their operation is sufficiently transparent"),
    O("14", "Human oversight by design", ACT + "14", "that they can be effectively overseen by natural persons during the period in which they are in use"),
    O("15", "Accuracy, robustness and cybersecurity", ACT + "15", "achieve an appropriate level of accuracy, robustness, and cybersecurity"),
    O("17", "Quality management system", ACT + "17", "Providers of high-risk AI systems shall put a quality management system in place"),
    O("72", "Post-market monitoring", ACT + "72", "Providers shall establish and document a post-market monitoring system"),
    O("73", "Reporting serious incidents", ACT + "73", "Providers of high-risk AI systems placed on the Union market shall report any serious incident"),
]
_CONFORMITY = {  # Art 43 by route
    "annex_i": O("43", "Conformity assessment under the Annex I legislation", ACT + "43", "the provider of the system shall follow the relevant conformity assessment procedure"),
    "biometrics": O("43", "Conformity assessment (Annex III point 1)", ACT + "43", "For high-risk AI systems listed in point 1 of Annex III"),
    "annex_iii": O("43", "Conformity assessment based on internal control", ACT + "43", "providers shall follow the conformity assessment procedure based on internal control"),
}
_TRANSPARENCY = {  # Art 50 trigger -> (who owes it, obligation)
    "G1": ("provider", O("50.1", "Tell people they are interacting with an AI system", ACT + "50", BY_ID["G1"].anchor)),
    "G2": ("provider", O("50.2", "Mark synthetic content as AI-generated, machine-readably", ACT + "50", BY_ID["G2"].anchor)),
    "G3": ("deployer", O("50.3", "Inform people exposed to emotion recognition or biometric categorisation", ACT + "50", BY_ID["G3"].anchor)),
    "G4": ("deployer", O("50.4", "Disclose deep fakes as artificially generated or manipulated", ACT + "50", BY_ID["G4"].anchor)),
    "G5": ("deployer", O("50.4b", "Disclose AI-generated text published to inform the public", ACT + "50", BY_ID["G5"].anchor)),
}
_LITERACY = O("4", "AI literacy of staff", ACT + "4", "shall take measures to support the development of AI literacy")


def obligations(decision: dict, answers: dict[str, str]) -> list[Obligation]:
    """The obligations that follow from a classify() decision. Pure; an unclear role lists both sides (fail closed)."""
    tier, role = decision["risk_tier"], decision["role"]
    if tier in ("out_of_scope", "unclear"):
        return []
    if tier == "prohibited":
        return [O("5", "Stop placing on the market, putting into service or using the practice", ACT + "5",
                  "The following AI practices shall be prohibited")]
    yes = lambda q: answers.get(q) == "yes"  # noqa: E731
    if yes("A7") and role not in ("provider", "both"):  # Art 2(10): a private person's own use carries no deployer duties
        return []
    provider, deployer = role in ("provider", "both", "unclear"), role in ("deployer", "both", "unclear")
    listed = [q.id for q in QUESTIONS if q.group == "E" and yes(q.id)]
    annex_iii = bool(listed) and listed != ["E2"]  # Arts 27, 49, 86 exclude Annex III point 2
    rows = []
    if tier == "high_risk":
        if provider:
            route = "annex_iii" if listed else "annex_i"
            route = "biometrics" if any(q.startswith("E1") for q in listed) else route
            rows += _PROVIDER_HIGH_RISK + [_CONFORMITY[route]]
            if annex_iii:
                rows.append(O("49.1", "Register the system in the EU database", ACT + "49",
                              "the provider or, where applicable, the authorised representative shall register"))
        if deployer:
            rows.append(O("26", "Deployer duties: instructions, human oversight, input data, monitoring, logs, informing people",
                          ACT + "26", "take appropriate technical and organisational measures to ensure they use such systems"))
            if annex_iii and (yes("B6") or yes("E5b") or yes("E5c")):
                rows.append(O("27", "Fundamental rights impact assessment", ACT + "27",
                              "shall perform an assessment of the impact on fundamental rights"))
            if annex_iii and yes("B6"):  # ponytail: B6 also covers private public-service bodies, which 49(3) does not
                rows.append(O("49.3", "Register the use in the EU database (public authority deployer)", ACT + "49",
                              "deployers that are public authorities, Union institutions, bodies, offices or agencies"))
            if annex_iii:
                rows.append(O("86", "Explain individual decisions to affected persons on request", ACT + "86",
                              "Any affected person subject to a decision which is taken by the deployer"))
    if decision["annex_iii_exception"] and provider:
        rows += [O("6.4", "Document why the Annex III system is not high-risk", ACT + "6",
                   "A provider who considers that an AI system referred to in Annex III is not high-risk shall document"),
                 O("49.2", "Register the system as not high-risk in the EU database", ACT + "49",
                   "for which the provider has concluded that it is not high-risk according to Article 6(3)")]
    rows += [o for q, (who, o) in _TRANSPARENCY.items() if q in decision["transparency"] and (provider if who == "provider" else deployer)]
    if yes("H2"):
        rows.append(O("53", "General-purpose AI model provider duties", ACT + "53", BY_ID["H2"].anchor))
        if yes("H3"):
            rows.append(O("55", "Systemic-risk model duties", ACT + "55",
                          "providers of general-purpose AI models with systemic risk shall"))
    return rows + [_LITERACY]


def legal_test(q: Question | Obligation) -> dict:
    """The one corpus passage under q.ref that contains q.anchor."""
    hits = [c for id_, c in law.corpus().items() if id_.startswith(q.ref + "/") and find_span(q.anchor, c["text"])]
    if len(hits) != 1:
        raise LookupError(f"{q.id}: anchor matches {len(hits)} passages under {q.ref}")
    return hits[0]


def render(questions: list[Question] = QUESTIONS) -> str:
    """Prompt text: each legal passage once, then the questions pointing at it."""
    tests = {q.id: legal_test(q) for q in questions}
    passages = {c["id"]: c for c in tests.values()}
    law_text = "\n\n---\n\n".join(f"[{c['id']}] {c['label']}\n{c['text']}" for c in passages.values())
    asked = "\n".join(f"{q.id}: {q.text} (legal test: {tests[q.id]['id']})" for q in questions)
    return f"## Legal tests\n\n{law_text}\n\n## Questions\n\n{asked}"
