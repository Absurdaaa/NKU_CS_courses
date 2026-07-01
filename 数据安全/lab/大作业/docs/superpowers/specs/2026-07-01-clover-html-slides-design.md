# Clover HTML Slides Design

## Goal

Build `clover_demo.html` as the formal presentation deck for a data security course paper report. The HTML file replaces a PPT, so it should behave like a slide deck rather than a long webpage.

The presentation is speaker-led. Slides should carry the main visual argument while the presenter explains details orally. Text density should stay low, but the principle section must be detailed enough to show real paper understanding.

## Scope

The deck explains the Clover paper:

- Harnessing Sparsification in Federated Learning: A Secure, Efficient, and Differentially Private Realization
- Topic: federated learning, top-k sparsification, secure aggregation, index/value privacy, distributed differential privacy

The deck does not:

- implement Clover's real cryptographic protocol;
- reproduce training experiments;
- prove the full security theorem;
- simulate exact distributed ORAM or DP accounting.

Interactive animations are concept demonstrations only. They should help explain the paper's key ideas, not claim to be protocol implementations.

## Format

- Single self-contained HTML file.
- Fixed 16:9 slide stage suitable for projection and screen recording.
- Keyboard navigation and visible previous/next controls.
- No vertical scrolling presentation flow.
- Low-density, speaker-led slides.
- 12 slides total.

## Slide Structure

1. **Title: Clover**
   - Paper title, venue, and keywords.
   - Establish the main thread: communication efficiency, secure sparse aggregation, and differential privacy.

2. **Background: Federated Learning's Privacy Illusion**
   - Explain that raw data stays local, but gradients and model updates can still leak information.

3. **Problem 1: Full Gradients Are Expensive**
   - Show why model dimension, number of clients, and training rounds amplify communication cost.
   - Include an animation where clients upload dense gradients.

4. **Starting Point: top-k Sparsification**
   - Explain how top-k selects the largest gradient coordinates.
   - Show dense gradients becoming sparse `(index, value)` pairs.

5. **Problem 2: Index Leakage**
   - Explain that value is not the only sensitive part; selected positions can reveal data distribution clues.
   - Include an attacker/server-view animation that highlights visible index patterns.

6. **Clover's Goal and Threat Model**
   - State what Clover protects: value, index, and individual client updates.
   - State what is revealed: only the aggregate result needed for model update.
   - Present the three-server non-collusion trust setting at a high level.

7. **Principle 1: Sparse Vector Representation**
   - Show sparse gradients as `(index, value)` entries.
   - Explain why different clients choose different top-k locations.
   - Explain why expanding everything into dense vectors would lose the communication benefit.

8. **Principle 2: Hidden Sparse Aggregation**
   - Show clients sending hidden/sharded sparse updates to three servers.
   - Servers collaborate, but no single visible path should expose a client's index/value.
   - Final visual output is an aggregate dense gradient, not individual sparse updates.

9. **Principle 3: Why Not Generic ORAM**
   - Compare generic ORAM-style access-pattern hiding with Clover's task-specific sparse aggregation.
   - Main message: ORAM is general but heavy; Clover is specialized and more efficient for this task.

10. **Principle 4: Distributed Differential Privacy**
    - Explain the separation of roles:
      - secure aggregation protects individual round updates;
      - differential privacy limits leakage from the final model/output.
    - Include a conceptual epsilon/noise/utility trade-off animation.

11. **Experiments and Limitations**
    - Combine key evaluation points and critical discussion.
    - Experiments: much faster than generic distributed ORAM baseline, lower client communication, utility close to vanilla FL with central DP.
    - Limitations: three-server trust assumption, system complexity, mainly top-k oriented, large-model scenarios need further validation.

12. **Summary**
    - One-sentence thesis: Clover integrates sparsification, secure aggregation, and differential privacy to balance communication efficiency and privacy in federated learning.
    - End with the system trade-off rather than a feature list.

## Interaction Boundary

Interactive or animated slides:

- Slide 3: dense gradient upload.
- Slide 4: top-k sparsification.
- Slide 5: index leakage view.
- Slide 7: sparse `(index, value)` representation.
- Slide 8: hidden sparse aggregation through three servers.
- Slide 10: DP noise and privacy-utility trade-off.

Static explanatory slides:

- Slides 1, 2, 6, 9, 11, 12.

The interactions should be deterministic and easy to reset. They should not require network access during presentation.

## Visual Direction

The deck should feel like a technical security presentation, not a marketing website. Use a clear visual grammar:

- clients, servers, gradients, hidden shares, and aggregate outputs as recurring visual objects;
- high contrast between exposed information and hidden information;
- restrained colors with sharp accents for risk, protection, and noise;
- large headings and concise phrases;
- no dense paragraphs on slides.

## Success Criteria

- The HTML can replace a PPT for a live course presentation.
- A listener can follow the story: FL background -> communication bottleneck -> top-k benefit -> index leakage -> Clover secure sparse aggregation -> DP -> evaluation and limitations.
- The principle section is detailed enough to show paper understanding without pretending to implement the protocol.
- The deck remains 12 slides and does not become a report page.
