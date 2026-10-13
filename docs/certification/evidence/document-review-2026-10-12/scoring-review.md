# Independent comparison scoring — 2026-10-12

The experimental guidance passes the factual floor but does not establish the
required concrete improvement over both baseline arms. All three arms cover every
claim, catch every planted issue, preserve unresolved conflicts and accept the
clean control. The smallest justified placement is the existing Skills, with the
explicit generic checklist available for requested checklist reviews. This
comparison does not justify a new Skill or module.

## Method and denominators

A separate lead-model reviewer read the frozen [oracle](oracle.json),
[commitment](oracle-commitment.json), all nine case files, [run ledger](runs.json)
and all 18 first reports. Findings were assessed from their actual reasoning and
source passages. This is human-readable, judgment-based scoring; the JSON is a
record of that assessment, not a mechanical truth validator. The scorer wrote
only this review and [scores.json](scores.json), preserving every first report.

There are three synthetic cases, six claims per case, three arms and two fixed
repetitions: 18 reports. The three-case set contains **eight material issues**
(four in case-01, four in case-02, none in case-03). Repeating the set twice gives
**16 issue opportunities and 36 claim assessments per arm**, with two clean-control
reports per arm. These repeated opportunities are not 16 independent defects or
36 independent source claims.

A covered claim must receive a substantive assessment; a caught issue must identify
the actual problem. Citation accuracy is scored once per claim against the source
passage, giving 36 citation assessments per arm. A useful correction provides a
replacement fact, an evidence limitation, removal/substantiation advice, or enough
specific guidance to repair the claim using the packet; a fully rewritten sentence
is not required. False material findings mean substantive unsupported defects or
incorrect factual corrections. Unnecessary labels and optional scope advice are
recorded separately. Unsupported precision and unavailable measurement are not
classified as proof that the underlying quantity is false.

## Results

| Metric | Current Skills | Generic checklist | Experimental |
|---|---:|---:|---:|
| Claims substantively covered | 36/36 | 36/36 | 36/36 |
| Material conclusions correct | 36/36 | 36/36 | 36/36 |
| Planted material issues caught | 16/16 | 16/16 | 16/16 |
| Missed planted issues | 0/16 | 0/16 | 0/16 |
| False material findings | 0 | 0 | 0 |
| Claim-level source citations accurate | 36/36 | 34/36 | 36/36 |
| Useful issue corrections | 16/16 | 16/16 | 16/16 |
| Supersession claims correctly handled | 4/4 | 4/4 | 4/4 |
| Unresolved proposal conflicts preserved | 4/4 | 4/4 | 4/4 |
| Clean-control reports correct | 2/2 | 2/2 | 2/2 |
| Non-material label/presentation defects | 2 | 2 | 0 |
| Human reminders recorded in run ledger | 0 | 0 | 0 |
| Report words, total across six reports | 1,150 | 1,445 | 1,464 |

The two conflict denominators split case-02: launch/budget supersession and
retention/capacity conflict, each assessed in both repetitions. False material
findings are counted across all six reports per arm, including both clean controls;
all arms also have zero false material findings specifically on the controls.
Word counts measure output length only, not runtime tokens, cost, latency or savings.

Every report's six claim assessments, excerpt, report line, citation judgment,
issue credit and caveats are retained in `scores.json`. Oracle, all nine case,
all 18 report and all 18 prompt hashes match the recorded commitments/ledger.
These checks establish preserved bytes and run identity, not factual truth.

## Passage evidence and differences

The substantive problem detection ties. For example, [current case-01 r1](reports/01-case-01-current-r1.md)
L4–L7 corrects the respondent denominator, rejects unsupported monthly savings,
rejects causality/generalization, and treats complaints as unmeasured. The same
four issues appear in [checklist case-01 r2](reports/15-case-01-checklist-r2.md)
L4–L7 and [experimental case-01 r2](reports/12-case-01-experimental-r2.md) L6–L9.
The latter says the exact savings cannot be established and asks for assumptions
and a calculation before presenting an estimate; it does not prove zero savings.

All arms use the approved amendment for launch and budget while retaining the
unchanged coverage and training owner. They also expose both retention proposals
and both capacity estimates without choosing a winner. See [current case-02 r2](reports/11-case-02-current-r2.md)
L3–L8, [checklist case-02 r1](reports/02-case-02-checklist-r1.md) L3–L8 and
[experimental case-02 r1](reports/05-case-02-experimental-r1.md) L7–L12.
Experimental case-02 r1 labels finality/agreement claims `Insufficient`, while
[r2](reports/14-case-02-experimental-r2.md) L10–L11 labels them `Contradicted`.
Both explanations correctly preserve unresolved proposals. This is a permissible
classification difference, not a substantive finding that either proposed number
is impossible.

One checklist report has a traceability defect: [case-02 r2](reports/17-case-02-checklist-r2.md)
L3–L4 correctly supplies November 10 and 84,000 credits but cites `amendment.md L1`
for those replacements. [The source](cases/case-02/amendment.md) L1 establishes the
amendment's date and supersession scope; the replacement values are on L2. Q1 and
Q2 therefore fail passage-location accuracy even though their material conclusions
and corrections are correct. The other checklist repetition gives L1–L2 correctly.

Current case-01 [r1](reports/01-case-01-current-r1.md) L3 and
[r2](reports/18-case-01-current-r2.md) L3 each say **“Correct the percentage”** for
Q1, which already contains the correct 25%. Each explanation immediately says
25% is supported and does not propose a false value, so these are two unnecessary
correction-label defects, not false material numeric findings. The checklist's
[case-01 r1](reports/04-case-01-checklist-r1.md) L3 calls Q1 partly supported and
requests sample-scope wording even though the oracle accepts it. Its qualifying
explanation is accurate, so this is non-material advice rather than a substantive
error. [Checklist clean-control r2](reports/10-case-03-checklist-r2.md) L3 refers to
“suggested corrections,” but every claim passes and L12 expressly says none is
required; that is the second checklist presentation defect.

Experimental reports consistently use explicit dispositions and introduce full
coverage; their case-02 tables put claim, evidence and correction together.
This improves presentation and avoids the noted label defects. Current already
covers every Q locator with accurate passages and useful guidance, however, so
these formats add no issue recall, source accuracy or reminder advantage over
that baseline. They also use 1,464 report words versus current's 1,150. No report
provides evidence of reduced human effort or runtime cost.

All six clean-control reports preserve the six supported claims and evidence
limits. For representative passages, [current r2](reports/13-case-03-current-r2.md)
L3–L10 says no corrections are needed, [checklist r1](reports/09-case-03-checklist-r1.md)
L3–L10 passes the claims, and [experimental r1](reports/03-case-03-experimental-r1.md)
L3–L10 says all six are supported. None treats missing complaint data as zero
complaints or unmeasured savings as zero savings.

## Acceptance and smallest next action

Experimental meets the planted-issue, citation and clean-control floors. It fails
the separate retention condition of demonstrating a concrete improvement over
**both** baselines: material correctness and reminders tie current, and current's
citations are equally accurate. The checklist's two locator mistakes should be
visible, rather than converted into material errors to manufacture an experimental
win. A tie favors current Skills or the explicitly supplied checklist.

Recommend current Skills as the best passing form for the required fresh no-save
continuation. Final retention remains conditional on that separate inventory check,
which this scorer has not executed or assessed. If a reusable delivery example is
wanted afterward, use the existing generic evidence checklist with the existing
checklist Skill and ask for an actual passage-locator check. Keep that checklist
explicit in the request. No new module, new active Skill or payload migration is
justified by these results.

## Limits and outstanding verification

Only three synthetic cases were evaluated, using the same author-model lineage
for cases, guidance and participant reports. The separate reviewer supplies a
second assessment but does not make the experiment independent of that lineage.
The oracle was hidden from supplied packets until execution completed; native
filesystem/tool-root isolation was unavailable. **Enforced blinding is not claimed.**
The comparison is input-hidden, not demonstrably blind.

The run ledger attributes requested `gpt-6-luna` at `medium`; native dispatch
accepted the request. The effective runtime model and effort were not independently
observed. These findings are about the retained reports under the recorded request,
not a certified model/effort comparison.

Short supplied Markdown does not qualify Library retrieval, PDF parsing, native
discovery, installation, live-document workloads or AI-app/provider retention.
This scoring review does not establish the no-save continuation, full-suite result,
CI, remote merge or release readiness. The lead owns those remaining checks.
There is no blocker to completing this scoring artifact; specialized retention
remains unjustified, and the continuation is still required before final retention.
