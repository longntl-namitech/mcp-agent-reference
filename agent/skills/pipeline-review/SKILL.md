---
name: pipeline-review
description: Review the deal pipeline by stage, flag stalled or overdue work, and summarize revenue. Use when asked how the pipeline looks.
---

# Pipeline review

Use this when the user wants a picture of the sales pipeline.

1. Call `search_tools` with "pipeline by stage" to find the report tools, then fetch the stage breakdown and top deals.
2. Stages run in order: lead, qualified, proposal, won, lost. Report counts and value per stage.
3. Fetch overdue tasks and name the deals or companies they belong to.
4. Finish with three short sections: where the pipeline is healthy, where it is stuck, and the next action for each stuck deal.

Only read data. If the user then asks to move a deal, use the deal tools; the user will be asked to approve the change.
