# Compliance notes (Kenya)

This is a practical checklist, not legal advice. Have a Kenyan lawyer review your use before launch.

## Data protection (Data Protection Act, 2019)

- **Roles.** KRA is the data controller for its records. By collecting PINs and ID numbers from your
  users and sending them to KRA, you are also a controller (or processor, if you do it for a client).
  Check whether you must register with the Office of the Data Protection Commissioner (ODPC).
- **Lawful basis and consent.** Tell users why you verify their PIN and obtain consent or document
  another lawful basis. The template's `consent` field makes your server confirm this per request.
- **Minimisation.** Send KRA only what is needed. Store the outcome (found/not found, time, reference)
  rather than KRA's full response. Leave `INCLUDE_RAW_RESPONSE=false` unless you need it.
- **Retention.** Decide how long you keep results, and delete them on schedule.
- **Security.** Encrypt in transit and at rest, restrict access, and keep secrets out of Git and logs.
  Complete a data protection impact assessment where your processing warrants one.
- **Breach readiness.** Know who to notify and how fast if credentials or data leak.

## KRA terms

- Use only KRA's official gateway and follow its terms, rate limits and acceptable-use rules.
- Do not resell or expose KRA data beyond what your approval covers.
- Do not scrape iTax or bypass its protections.

## Product wording

Say "KRA PIN found" or "not found", not "verified identity" or "tax compliant". Those claims need other evidence.
