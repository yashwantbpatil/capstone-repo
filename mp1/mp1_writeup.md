
# Prompt Strategy Evaluation & Reflections

## 1. Which Strategy Won, and on What Dimension?
* **Overall Winner (Accuracy):** The **Few-shot** prompt strategy won overall, it achieved the hightest accuracy and Judge score
* **Dimension Breakdown:**
  * **Accuracy:** Few-shot achieved the strongest overall performance.
  * **Parse rate:** All strategies performed best 
  * **Cost:** Zero shot has achieved lowest cost

## 2. What Surprised You?
* **Few-shot outperformed other strategies:** Providing concrete examples noticeably improved results compared to the other prompt approaches.
* **Structured prompting fell short of expectations:** I expected structured prompting to deliver better results across **Accuracy**, **Parse rate**, and **Cost**, but it did not outperform as anticipated.
* **The Chain of Thought strategy surprisingly exhibits the highest latency among all strategies.**


## 3. Capstone Domain Choice: First Strategy to Reach For
* **Chosen Strategy:** **Structured prompt**
* **Reasoning:** For my capstone domain, I would start with a Structured Prompting strategy to establish predictable output formats and schema consistency, providing a reliable baseline for further experimentation and refinement. Cost, latency, and accuracy are key factors to consider when selecting a prompting strategy. Although Structured Prompting may offer slightly lower accuracy than Few-shot Prompting, its accuracy can potentially be improved through iterative refinement, system prompt tuning, and optimization. This makes it a good starting point while balancing consistency, performance, and cost.

## 4. Next Steps (With Another Day)
* **Expand and diversify the dataset:** I would increase the number of job snippets beyond 10 and include few more messy, real-world edge cases.
* **Debug and refine inaccuracies:** I would print out the inaccurate extractions, analyze where and why they failed, and refine the prompts accordingly.
* **Track full end-to-end cost:** I will also track total end to end cost (extraction + judge),  currently the comparison table only tracks extraction cost per strategy, I would also report judge_cost also in the comparison table
