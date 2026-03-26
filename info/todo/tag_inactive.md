# No recent commits tags - inactive

Add to script command witch will add "inactive"

Requirements:

1. Propose a metric or heuristic that uses commit history to estimate that an employee is no longer active.
2. The metric should not rely only on a fixed threshold. It should also account for the employee’s historical commit pattern, such as:

   * last commit date
   * typical interval between commits
   * activity over the last 30 / 60 / 90 days
3. Include:

   * the metric definition
   * suggested formula or scoring model
   * threshold examples for interpretation
   * edge cases and limitations
4. Make it clear that this is only a probabilistic signal, not proof that the employee left the company, because a person may be on vacation, moved into management, changed projects, or work outside tracked repositories.
5. Use the following English tag name for such employees:

   * `inactive`
6. Explain why this tag is preferable to stronger labels such as “terminated” or “offboarded”.

Preferred output format:

* short explanation of the metric
* formula / scoring logic
* threshold interpretation
* edge cases and limitations
* final recommendation

The tone should be practical and suitable for an internal engineering analytics system.
