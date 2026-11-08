# Research stage R6: theory builder

When the research has a shape, turn it into a theory a reader can use and a critic can attack.

    python3 scripts/ghostwriter.py scaffold <book> theory --name "..."

Sections (the `check-research` gate checks the structure):
1. **Bottom line:** three bullets.
2. **Definitions:** every term and every scoring axis. A useful pair: *efficacy* (does it work
   when done as intended?) vs. *effectiveness* (does a real, busy person actually keep doing it?).
3. **Propositions:** 3 to 6, each as `### P1 ...` with **Mechanism**, **Evidence** (graded, with
   keys) and **Wrong if:** an observation concrete enough to go and check. A proposition no
   observation could falsify is not a proposition.
4. **Decision rule:** `## Decision rule: The <Name> Test`. A short ordered list of yes/no
   questions a reader applies to their own case. Name it; readers remember named tests.
5. **Predictions:** 5 to 8, each with a date ("by end of 2028"), the proposition it tests, and
   how we would know.
6. **Scoring:** if practices are scored on the axes, say these are **judgment calls, not
   measurements**, who scored them and by what rule.
7. **Where the evidence is thin:** an honest numbered list. Name the strongest and weakest links.

Ground the theory in the coverage grid and the scorecard, and cite the author's words (`V###`)
where the theory rests on their belief rather than on evidence. Say which is which.
