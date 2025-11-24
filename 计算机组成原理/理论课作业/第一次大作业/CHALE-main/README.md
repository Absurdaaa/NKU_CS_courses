# CHALE
Controlled HALlucination-Evaluation (CHALE) Dataset

## Detailed Generation of CHALE

The Controlled Hallucination-Evaluation (CHALE) dataset is constructed based on the "[Google Natural Questions](https://ai.google.com/research/NaturalQuestions/visualization)" dataset The original dataset comprises approximately 307,000 training samples. For CHALE, we meticulously selected a subset of around 100,000 samples from these training data. Each selected entry in CHALE contains the following essential components, which are integral to our evaluation framework:

* **Question text**: This is the natural question posed in the dataset.

* **Short Answer**: A concise and accurate answer to the natural question. This brief response provides a straightforward answer to the query.

* **Long Answer**: In contrast to the short answer, this is an elongated and more detailed response, offering a comprehensive explanation or context to the natural question.

* **Additional Information**: This includes crucial metadata such as the annotation ID, document resource URL, and example ID. This information is necessary for seamless integration and retrieval of data from the official dataset.

### Dataset Generation Methodology

The construction of the CHALE dataset follows a systematic approach aimed at generating question-answer pairs that exhibit potential hallucinations. Each response in our dataset follows the format: ``Short Answer + Detailed Information/Reasoning``. Within this framework, the accuracy of the short answer is utilized as an indicator of truthfulness. In contrast, the relevance and coherence of the detailed information or reasoning segment are employed to gauge the informativeness of the response. To achieve this structure, we deconstruct each comprehensive answer into its sentences. Then, one sentence is randomly chosen as the detailed information/reasoning component.

In the CHALE dataset, a standard non-hallucinated answer combines the pertinent short answer with concise reasoning or additional information derived from the more extensive corresponding long answer. To generate hallucinated responses, we adopt a strategic mismatch approach. This involves either misaligning the short answer or the informative segment with the original question, instead aligning it with a nearby yet distinct question. 

### Detailed Generation Process

We employed the following methodical steps to construct the CHALE dataset:

* **Step 1: Collection of Raw Data.** Our initial step involved curating samples from the Google Natural Questions dataset. We specifically targeted entries that included both long and short answers. We eliminated answers formatted as tables or markdowns to ensure uniformity in the data structure for subsequent analysis.

* **Step 2: Generation of Informative and Uninformative Answers.** We focused on the central content of each selected long answer by removing its introductory and concluding sentences. The remaining text was segmented into individual sentences, forming the basis for the informative components in our dataset. This process yielded approximately 8.74 sentences per answer, each potentially serving as an informative segment.

* **Step 3: Implementation of Random Matching Rules.** We established a set of criteria for deliberately mismatching questions and answers to induce hallucinations. Each question from the dataset was paired with one from its 20 nearest neighbors, adhering to a similarity index between 0.2 and 0.8. This strategy produced, on average, 4.83 suitable mismatched questions for each original question.
 
* **Step 4: Synthesis of Answers.** We constructed multiple non-hallucinated answers for each question, ensuring their truthfulness and informativeness. In addition, a set of hallucinated answers was created for each question by applying our random matching rules. This involved selecting mismatched questions and answers from the pool of candidates.

**An example**

```
Question: who played Mantis Guardians of the Galaxy 2?

Short Answer: Pom Klementieff.

Long Answer: Pom Klementieff (born 3 May 1986) is a French actress. She was trained at the Cours Florent drama school in Paris and has appeared in such films as Loup (2009), Sleepless Night (2011), and Hacker's Game (2015). She plays the role of Mantis in the film Guardians of the Galaxy Vol. 2 (2017) and will appear in the same role in the film Avengers: Infinity War (2018).

Non-Hallucinated Answer: Pom Klementieff. She was trained at the Cours Florent drama school in Paris and has appeared in such films as Loup (2009), Sleepless Night (2011), and Hacker's Game (2015).

Hallucinated Answer: Karen Gillan. 2 (2017) and will appear in the same role in the film Avengers: Infinity War (2018). 
```


### Basic Information

In CHALE, each sample contains the natural question, the short correct answer, a long answer, an annotation ID, etc. We further provide each question with a non-hallucinated answer (correct and informative), a hallucinated answer (incorrect and uninformative), and a half-hallucinated answer (either incorrect yet informative or correct yet uninformative). We include the statistics in the Table below.

<table style="width:50%; margin:auto;">
  <caption style="caption-side: bottom; margin-top: -0.2in;">Basic statistics of five answer types in CHALE dataset. We report a subset of CHALE for experiment purposes, including 940 questions in all.</caption>
  <tr>
    <th style="background-color: #4CAF50; color: white;">Answer Type</th>
    <th style="background-color: #4CAF50; color: white;">Word Count</th>
    <th style="background-color: #4CAF50; color: white;">Unique Word Count</th>
    <th style="background-color: #4CAF50; color: white;">Characters Length</th>
  </tr>
  <tr>
    <td style="background-color: #f2f2f2;">Short</td>
    <td style="background-color: #f2f2f2;">4.49</td>
    <td style="background-color: #f2f2f2;">4.15</td>
    <td style="background-color: #f2f2f2;">24.72</td>
  </tr>
  <tr>
    <td style="background-color: #ffffff;">Long</td>
    <td style="background-color: #ffffff;">259.64</td>
    <td style="background-color: #ffffff;">95.89</td>
    <td style="background-color: #ffffff;">1111.28</td>
  </tr>
  <tr>
    <td style="background-color: #f2f2f2;">Non-Hallu</td>
    <td style="background-color: #f2f2f2;">33.57</td>
    <td style="background-color: #f2f2f2;">26.17</td>
    <td style="background-color: #f2f2f2;">170.49</td>
  </tr>
  <tr>
    <td style="background-color: #ffffff;">Mid-Hallu</td>
    <td style="background-color: #ffffff;">33.54</td>
    <td style="background-color: #ffffff;">26.24</td>
    <td style="background-color: #ffffff;">169.79</td>
  </tr>
  <tr>
    <td style="background-color: #f2f2f2;">Hallu</td>
    <td style="background-color: #f2f2f2;">33.15</td>
    <td style="background-color: #f2f2f2;">26.06</td>
    <td style="background-color: #f2f2f2;">167.66</td>
  </tr>
</table>


## Getting Started (Code)
* ``hallucinated_ans_final_filtered.json``: includes approximately 1000 QA samples. **The preprint will come soon!**

The dataset is in a dictionary format, which includes the following keys:

**Question**, **Short_ans**, **Long_ans**, **halu**, **mid-halu**, **non-halu**

* ``start_code.py``: a start code to load the data.
