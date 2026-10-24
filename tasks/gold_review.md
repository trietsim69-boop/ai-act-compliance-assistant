# Gold review (Checkpoint A)

Generated from `evals/cases.json` and `evals/private/cases.json` (private, git-ignored: marked *). Obligation status: unclear = documents silent (met would be wrong), gap = documents show it missing, met = documents show it done, any = contestable. Provider set = Arts 9-15, 17, 43, 49, 72, 73.

| Case | chars | AI system | Tier | Role | GPAI | Obligations (article:status) | Deciding provision / note |
|---|---|---|---|---|---|---|---|
| hr_screening | 2,929 | – | high_risk | – | – | 26:any, 86:unclear, 4:unclear | Annex III 4(a) recruitment; deployer (vendor develops) |
| customer_chatbot | 2,382 | – | limited_risk | – | yes | 50:unclear, 4:unclear | Art 50(1) chatbot; notice only drafted |
| workplace_emotion_detection | 2,652 | – | prohibited | – | – | 5:gap | Art 5(1)(f) emotion inference at work, no medical/safety purpose |
| spam_filter | 1,577 | – | minimal_risk | – | no | 4:unclear | minimal risk; Art 4 only |
| llm_report_generator | 2,109 | – | – | – | yes | 4:unclear | downstream GPAI use, no Art 53 duties; Art 50(2) arguable so left out |
| predictive_maintenance | 1,873 | – | minimal_risk | – | no | 4:unclear | not a safety component on the documents; Art 4 only |
| exam_proctoring | 624 | yes | high_risk | provider | – | provider set:unclear, 4:unclear | Annex III 3(d); provider |
| university_admissions | 591 | yes | high_risk | deployer | – | 26:gap, 86:unclear, 4:unclear | Annex III 3(a); deployer; low scores never reach a human (26(2)) |
| consumer_credit_scoring | 489 | yes | high_risk | both | – | provider set:unclear, 26:gap, 27:unclear, 86:unclear, 4:unclear | Annex III 5(b); both; Art 27 applies to 5(b) deployers; automatic declines |
| life_insurance_pricing | 461 | yes | high_risk | – | – | 26:unclear, 27:unclear, 86:unclear, 4:unclear | Annex III 5(c); deployer duties; provider role contested |
| retail_face_matching | 544 | yes | high_risk | deployer | – | 26:unclear, 4:unclear | Annex III 1(a) remote biometric identification; deployer; not law enforcement |
| deepfake_marketing | 492 | – | limited_risk | deployer | – | 50:gap, 4:unclear | Art 50(4) deep fake; labelling undecided |
| medical_imaging_triage | 447 | yes | high_risk | provider | – | provider set, 43:any, 4:unclear | Art 6(1) + Annex I MDR, notified body; provider |
| invoice_rules_engine | 525 | no | – | – | no | none | not an AI system (fixed human-written rules) |
| municipal_social_scoring | 531 | yes | prohibited | deployer | – | 5:gap | Art 5(1)(c) social scoring |
| smart_toy_challenges | 470 | yes | prohibited | provider | – | 5:gap | Art 5(1)(b) exploiting children's age |
| predictive_policing_profiles | 471 | yes | prohibited | provider | – | 5:gap | Art 5(1)(d) crime prediction from profiling alone |
| emergency_call_triage | 443 | yes | high_risk | deployer | – | 26:gap, 4:unclear | Annex III 5(d); deployer; no monitoring since installation (26(5)) |
| gig_task_allocation | 474 | yes | high_risk | both | – | provider set:unclear, 26:gap, 86:unclear, 4:unclear | Annex III 4(b); both; couriers not informed (26(11)), automatic deactivation |
| customer_call_emotion | 545 | yes | high_risk | deployer | – | 26:unclear, 50:gap, 4:unclear | Annex III 1(c) emotion recognition; deployer; customers not told (50(3)) |
| cv_parser_procedural | 526 | yes | minimal_risk | provider | no | 6:any, 49:unclear, 4:unclear | Annex III 4(a) but Art 6(3)(a) narrow procedural task, no profiling; Art 6(4) record + 49(2) registration |
| cv_ranking_profiling | 399 | yes | high_risk | provider | no | provider set:unclear, 4:unclear | Annex III 4(a); profiling of applicants overrides any Art 6(3) claim |
| control_room_distress_safety | 589 | yes | high_risk | deployer | no | 26:unclear, 50:met, 4:unclear | Art 5(1)(f) safety exception, so not prohibited; still Annex III 1(c) emotion recognition; 50(3) informing done |
| university_emotion_research | 389 | yes | out_of_scope | provider | no | none | Art 2(6) sole purpose of scientific research and development |
| us_only_tenant_screening | 359 | yes | out_of_scope | both | no | none | Art 2(1): provider and deployer outside the EU, output not used in the EU |
| white_label_hiring | 457 | yes | high_risk | provider | no | provider set:unclear, 4:unclear | Art 25(1)(a): rebranding a high-risk system makes the agency its provider |
| welfare_fraud_risk_score | 502 | yes | high_risk | deployer | no | 26:unclear, 27:unclear, 49:unclear, 86:unclear, 4:unclear | Annex III 5(a); public-body deployer: Art 27 rights assessment and Art 49(3) registration; profiling, no Art 6(3) |
| email_writer_on_llm | 385 | yes | limited_risk | provider | yes | 50:unclear, 4:unclear | Art 50(2) synthetic text marking for the provider; downstream GPAI user, no Art 53 duties |
| sales_dashboard_statistics | 386 | no | – | – | no | none | not an AI system: descriptive statistics and visualisation (AI system guidelines, basic data processing) |
| gig_allocation_in_vat_pack | 121,027 | yes | high_risk | both | – | provider set:unclear, 26:gap, 86:unclear, 4:unclear | needle in a haystack: the gig_task_allocation facts (Annex III 4(b)) in one section of ~120k chars of VAT guidance |
| govuk_chat_record | 22,247 | yes | out_of_scope | both | yes | none | UK government chatbot for UK users: Art 2(1) territorial scope; hosting in AWS Ireland is processing, not use of the output in the Union (contestable). Built in-house on Claude Sonnet 4; Art 50(1) would apply in the EU. |
| duo_student_finance_profile * | 192,224 | no | – | – | no | none | not an AI system: the audit states the risk profile is not self-learning and uses no AI; criteria set by hand. 190k chars about profiling and indirect discrimination pull towards high-risk. |
| amsterdam_slimme_check * | 13,606 | yes | high_risk | – | no | 26:any, 27:any, 49:unclear, 86:unclear, 4:unclear | Annex III 5(a) welfare checks by a public body, model trained on historical data, profiling so no Art 6(3); IAMA done (Art 27 contestable), human review documented; out of use since 2023-09 |
