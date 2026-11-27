> **Note:** This document is a conceptual project brief and idea overview only—not a strict implementation spec or a coding rules file.

# NetraCare Eye Clinic: AI Front Desk 

this project you build step by step Iterations across the whole cycle. 

NetraCare is a fictional clinic. All doctors, patients, staffs and data in this project are synthetic. 

-----

**01.**

## Project objective 

**Build an AI front desk for NetraCare that answers patient questions, routes each patient to the right specialist and manages appointments, while keeping staff in control and never giving medical advice.** 

-----

**02.**

## The problem today

NetraCare has 5 doctors. Its front desk staff handle every call, walk-in and message all by themselves. 

### Patients wait on hold 

Most calls are the same questions: timings, fees, what to bring, how long dilation lasts. 

### Wrong specialist 

Patients describe symptoms in their own words and get booked with a doctor who then refers them on. 

### Slots go to waste 

Patients who can't come rarely call to cancel, so their slot sits empty. 

### Staff are the bottleneck 

Every booking, change and cancellation goes through the front desk. 

-----

**03.**

## The clinic 

Open Monday to Saturday, 9 AM to 6 PM, closed for lunch 1 to 2 PM, closed Sundays and listed holidays. The day has two sessions: `AM 09:00–13:00` and `PM 14:00–18:00` . 

### Doctors 

|`DOCTOR`|`SPECIALITIES`|
|---|---|
|Dr. Anand Rao|Cataract, General|
|Dr. Meera Iyer|Glaucoma, Cataract|
|Dr. Kiran Shah|Retina (diabetic eye, AMD), General|
|Dr. Fatima Khan|Cornea, Refractive (LASIK), Dry eye|
|Dr. Vikram Menon|Paediatric, Squint, General|


### Weekly OPD schedule 

|`DOCTOR`|`MON`|`MON`|`TUE`|`TUE`|`WED`|`WED`|`THU`|`THU`|`FRI`|`FRI`|`SAT`|`SAT`|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|Dr. Rao|`AM`|`PM`|`AM`|`PM`|`AM`|`PM`|`SX`|`PM`|`AM`|`PM`|`AM`|`PM`|
|Dr. Iyer|`AM`|`PM`|`SX`|`SX`|`AM`|`PM`|`off`|`off`|`AM`|`PM`|`AM`|`PM`|
|Dr. Shah|`AM`|`PM`|`AM`|`PM`|`AM`|`SX`|`AM`|`PM`|`AM`|`PM`|`off`|`off`|
|Dr. Khan|`SX`|`SX`|`AM`|`PM`|`AM`|`PM`|`AM`|`PM`|`AM`|`PM`|`AM`|`PM`|
|Dr. Menon|`AM`|`PM`|`AM`|`PM`|`off`|`off`|`AM`|`PM`|`off`|`off`|`AM`|`PM`|


> `AM`/`PM` = OPD, bookable.
> `SX` = surgery, not bookable.
> `off` = Not at the clinic. 

-----

**04.**

## Rules the system must enforce 

Every booking must follow these rules. 

### Slots 

- New consultation: `20 min` . Follow-up: `10 min` . 

- No slots: from 1 to 2 PM, on Sundays, on listed holidays, or in a surgery session. 

- An appointment must finish by 1 PM (AM session) or 6 PM (PM session). 

- No double-booking a slot. 

### Booking 

- Bookings open up to 30 days ahead. 

- One active booking per patient per speciality. 

- A follow-up is booked with the doctor who saw the patient. 

- Patients are identified by mobile number and name. 

### Cancel and reschedule  

- Patients can cancel until 2 hours before the appointment. 

- A reschedule counts as cancel plus new booking, so the same 2-hour cut-off applies. 

- Inside 2 hours, the request goes to staff. 

### Doctor leave

- Leave cancels the affected slots. 

- Each affected patient is offered the next slot with the same or an overlapping specialist. 

- If no other doctor covers the speciality, offer the same doctor's next free slot. 

### No slot available 

- If no suitable slot is free within the 30-day window, 

- say so clearly. 

- A cancelled slot becomes free for anyone to book. 

-----

**05.**

## Who uses it 

|`ROLE`|`CAN DO`|
|---|---|
|Patient|Ask questions, describe symptoms, book, reschedule and cancel their own appointments.|
|Staff|Everything a patient can, for any patient. Book walk-ins, override rules and approve flagged actions. Manage doctors and holidays. See reports.|
|Doctor|See their own schedule and patient intake notes. Mark leave.|

-----

**06.**

## Scope 

### In scope 

- Enquiries and FAQs 

- Speciality routing from symptoms 

- Booking, rescheduling, cancelling 

- Staff dashboard 

- Intake summaries for doctors 

- Booking access for partner apps 


### Out of scope 

- Pharmacy and inventory 

- Diagnosis or treatment advice 

- Reading eye images or reports 

- Prescriptions 

- Billing and payments 

- Insurance claims 

-----

**07.**

## Safety rules (non-negotiable) 

1. Never name a likely condition or suggest treatment. Route to a speciality and say a doctor will assess. 

2. Red-flag symptoms always get the emergency response before any booking, and appear as urgent on the staff dashboard. 

3. Every answer about policy or procedure cites the clinic document it came from. If the documents don't say, the assistant says it doesn't know. 

4. Patients only ever see their own appointments and details. 

5. Use only the synthetic data provided. No real patient information, ever. 

> ### Examples of red-flag symptoms 
> 
> - Sudden loss of vision, in one or both eyes 
> 
> - A curtain or shadow moving across the vision 
> 
> - A sudden shower of new floaters or flashes of light 
> 
> - Chemical splash or any injury to the eye 
> 
> - Severe eye pain with headache, nausea or haloes around lights 

Example emergency response 

```
What you describe needs urgent attention. Please come to the clinic now or go to
the nearest emergency department. Our staff have been notified.
```

-----

**08.**

## What you will have at the end 

By the final demo, your NetraCare includes these parts. Each lists the course topics you apply to build it. 

### Clinic API 

(TOOLS)

Doctors, slots and appointments, with every rule enforced. Your agents call these as tools. 

sugession: `Python` `OOP` `FastAPI` `Pydantic` `Tool calling`


### Clinic MCP server 

(PARTNER ACCESS)

Exposes the core clinic APIs so partner apps, such as health aggregators, can book NetraCare from their own agents. 

sugession: `MCP` 

### Patient assistant 

(CORE AGENT)

Chat that answers questions, routes patients, writes intake summaries for doctors and books appointments. 

sugession: `LLM APIs` `Prompt engineering` `Agents: tools, memory, planning` `LangGraph` `Human-in-the-loop` `Skills` `Voice` `Multimodal`


### Clinic knowledge base 

(RAG)

Clinic policies and patient guides the assistant answers from, with citations. 

sugession: `Embeddings` `Vector DB` `Chunking` `Reranking` `LlamaIndex` `Graph RAG` `Agentic RAG`


### Staff dashboard 

Each doctor's day, urgent cases, approvals, overrides and rebooking patients when a doctor is on leave. 

sugession: `Frontend` `Async` `Human-in-the-loop`


### Proof of quality 

`EVALS AND OBSERVABILITY` Test results that prove the targets below, and a dashboard to monitor the live system. 

sugession: `RAGAS` `Offline online evals` `LangSmithOpik`

-----

**09.**

## How we will judge success 

|`MEASURE`|`TARGET`|
|---|---|
|Red-flag messages that trigger the emergency response|`100%`|
|Patients routed to the correct speciality (test set)|`≥ 90%`|
|Bookings that break a clinic rule|`0`|
|Policy answers that cite a clinic document|`100%`|
|Answers that name a condition or suggest treatment|`0`|

-----

**10.**

## How this project brief works 

This page is the overall brief. It describes the whole project and does not list everything you need to build. This is the idea of NetraCare Eye Clinic AI Front Desk project.

After each Iteration, you will receive detailed requirements for the capabilities to build next, using the context you have just learnt and built. Each set of requirements adds to your NetraCare from the previous Iteration module, so the project grows step by step. 

