# Intraoperative Physiological Monitoring Features Independently Predict Postoperative Transfusion with Robust Cross-Institutional Generalizability: A Retrospective Cohort Study with External Validation

---

## Abstract

**Background:**
Prediction models for postoperative transfusion rely primarily on preoperative variables, yet the independent and incremental predictive value of intraoperative physiological monitoring data — including cumulative threshold-based vital sign summaries and hematocrit trajectory — remains unclear, particularly regarding cross-institutional generalizability.

**Objective:**
To compare the discriminative performance and cross-institutional generalizability of preoperative, intraoperative, and combined feature sets for predicting packed red blood cell (pRBC) transfusion within 48 hours after surgery.

**Methods:**
This retrospective cohort study with external validation included 35,915 surgical cases from Seoul National University Hospital (SNUH, 2016–2019) and 579 cases from Seoul National University Boramae Medical Center (BMC) for independent external validation. Three CatBoost gradient boosting models were trained on the development set (2016–2018) and evaluated on a temporally held-out internal test set (2019) and the external set: Preoperative (43 features), Intraoperative (64 features including cumulative vital sign durations, static intraoperative variables, and time-weighted average hematocrit [TWA-Hct]), and Combined (107 features). Discrimination was assessed by AUROC with bootstrap 95% CI and pairwise DeLong tests.

**Results:**
Internally, the Combined model achieved an AUROC of 0.894 (95% CI: 0.882–0.906), the Intraoperative model 0.880 (0.867–0.893), and the Preoperative model 0.775 (0.755–0.794). Both the Intraoperative and Combined models significantly outperformed the Preoperative model (DeLong p = 2.08 × 10⁻²⁴ and p = 7.95 × 10⁻³⁹, respectively). The Combined model marginally outperformed the Intraoperative model internally (ΔAUROC = +0.014, p = 2.32 × 10⁻⁸), but this advantage was not statistically significant externally (ΔAUROC = +0.006, p = 0.626). Externally, the Combined model achieved the highest AUROC (0.882; 0.845–0.913), followed by Intraoperative (0.877; 0.834–0.914) and Preoperative (0.767; 0.704–0.823). Internal-to-external AUROC differences were small across all models (Preoperative: −0.008, Intraoperative: −0.004, Combined: −0.012). An ablation study confirmed that threshold-based vital sign durations alone (AUROC 0.772) provide discrimination comparable to preoperative features but require TWA-Hct and EBL for the full Intraoperative model's performance.

**Conclusions:**
Intraoperative features — particularly TWA-Hct, estimated blood loss, and cumulative vital sign durations — achieve discrimination comparable to the full combined model and generalize robustly across institutions. While preoperative variables provide minimal incremental benefit in discrimination, the Combined model demonstrated the best calibration, producing predicted probabilities that most closely approximate true event rates across the full risk spectrum. These findings support the use of intraoperative monitoring data for postoperative transfusion prediction, with the Combined model preferred when well-calibrated probability estimates are needed for clinical decision-making.

**Keywords:** postoperative transfusion, intraoperative monitoring, cumulative vital signs, time-weighted average hematocrit, machine learning, external validation

---

# 1. Introduction

*(To be written)*

---

# 2. Methods

## 2.1 Study Design and Data Sources

This was a retrospective cohort study with external validation. The study protocol was approved by the institutional review boards of the participating hospitals, and the requirement for informed consent was waived given the retrospective nature of the study.

**Internal dataset (SNUH).** Electronic health records and intraoperative vital sign waveforms were obtained from Seoul National University Hospital (SNUH) for all surgical cases performed between January 2016 and December 2019. Perioperative clinical data — including demographics, preoperative laboratory values, comorbidities, anesthesia type, and intraoperative fluid/transfusion records — were extracted from the hospital information system.

Continuous intraoperative vital sign data were collected using the Vital Recorder program (version 1.7.4), a free, lightweight software tool that automatically records high-resolution, time-synchronized physiological data from multiple anesthesia devices including patient monitors, anesthesia machines, and other bedside equipment [Lee & Jung, *Sci Rep* 2018;8:1527]. The Vital Recorder was installed on laptop computers connected to GE Solar 8000M/8000i patient monitors via serial ports in 10 operating rooms at SNUH. The software captured numeric parameters (non-invasive blood pressure [NIBP], heart rate [HR], peripheral oxygen saturation [SpO₂], and ST-segment values) at intervals of 1–7 seconds and stored them in the proprietary .vital file format. The data collection was conducted under a prospective registry study approved by the SNUH Institutional Review Board (H-1408-101-605; ClinicalTrials.gov NCT02914444).

The collected vital sign files were archived in the institutional VitalDB server (snuh.vitaldb.net), a high-fidelity multi-parameter vital signs database [Lee et al., *Sci Data* 2022;9:279]. For the present study, vital sign files matching each surgical case were retrieved from VitalDB using de-identified file identifiers, and the numeric vital sign tracks were extracted for feature computation.

**External dataset (BMC).** An independent dataset from Seoul National University Boramae Medical Center (BMC) was used for external validation. Intraoperative vital sign data at BMC were collected using the same Vital Recorder software installed on identical GE Solar 8000M/8000i patient monitors, ensuring that the vital sign acquisition pipeline — including signal types (NIBP, HR, SpO₂, ST), sampling intervals, and file format — was consistent between institutions. This dataset contained equivalent preoperative and intraoperative variables, although three fluid-management variables (crystalloid volume, colloid volume, and platelet concentrate) were not recorded and were set to zero. ASA Physical Status classification was supplemented from a supplementary source file when unavailable in the primary dataset.

## 2.2 Study Population

### 2.2.1 Internal Cohort

The initial screening identified 50,932 surgical cases from SNUH. Cases were sequentially excluded based on the following criteria (Figure 1):

1. No VitalDB file identifier available (n = 1,435)
2. No intraoperative NIBP monitoring data retrievable from VitalDB (n = 12,077)
3. Absence of HR, SpO₂, or ST-segment data (n = 2,933)
4. Duplicate file identifiers (n = 7)

After exclusions, **35,915 cases** constituted the final internal cohort. This cohort was temporally divided into a **development set** (2016–2018; N = 21,233; 878 postoperative anemia events [4.1%]) and a **held-out internal test set** (2019; N = 14,682; 596 events [4.1%]).

### 2.2.2 External Cohort

From BMC, 785 surgical cases were screened. After excluding 205 cases without vital sign files and 1 case without preoperative hematocrit data, **579 cases** formed the final external cohort (80 postoperative anemia events [13.8%]).

## 2.3 Outcome Definition

The primary outcome was postoperative anemia requiring transfusion, operationally defined as packed red blood cell (pRBC) transfusion within 48 hours after surgery. A binary label was assigned: positive (tf48 = 1) if any pRBC transfusion was administered within 48 hours of operating room discharge, and negative (tf48 = 0) otherwise.

## 2.4 Feature Engineering

A total of 107 predictor variables were constructed and organized into four clinically meaningful groups.

### 2.4.1 Preoperative Features (43 variables)

Preoperative features were extracted from the EHR and categorized into four subcategories:

**Demographics and surgical information (5 variables).** Sex (female = 1, male = 0), age (years), weight (kg), height (cm), and emergency surgery status (emergency = 1, elective = 0).

**Preoperative laboratory values (15 variables).** Hemoglobin (Hb), hematocrit (Hct), platelet count, blood urea nitrogen (BUN), creatinine, prothrombin time (PT), PT-INR, activated partial thromboplastin time (aPTT), albumin, aspartate aminotransferase (AST), alanine aminotransferase (ALT), sodium, potassium, glucose, and estimated glomerular filtration rate (eGFR).

**Comorbidities and clinical history (14 variables).** Thirteen binary indicators for pre-existing conditions — hypertension, diabetes mellitus, tuberculosis, liver disease, chronic obstructive pulmonary disease (COPD), asthma, heart disease, thyroid disease, renal disease, hematologic disease, vascular disease, neurologic disease, and other diseases — along with the American Society of Anesthesiologists Physical Status (ASA-PS) classification.

**Anesthesia type and surgical category (9 variables).** Two binary variables for surgical category (major surgery, minor surgery) derived from the surgical code. Anesthesia type was represented as seven one-hot encoded binary variables: combined spinal–epidural, epidural, general, intravenous regional, monitored anesthesia care (MAC), nerve block, and spinal anesthesia.

### 2.4.2 Threshold-Based Vital Sign Duration Features (50 variables)

Intraoperative vital sign waveforms were retrieved from the institutional VitalDB server. For each patient, continuous monitoring data were filtered to the interval between surgical start and end. Rather than using conventional summary statistics (mean, minimum, maximum), we computed threshold-based duration features — the total time during which each vital sign parameter exceeded or fell below predefined clinical thresholds. This approach quantifies the physiological burden of intraoperative derangement as a cumulative "dose," analogous to the concept of hypotension burden in the anesthesia literature.

**Hemodynamic instability indices (25 variables).** Total duration (in minutes) during which blood pressure fell below predefined thresholds:
- Systolic blood pressure (SBP): 8 thresholds from 50 to 120 mmHg in 10 mmHg increments
- Diastolic blood pressure (DBP): 8 thresholds from 10 to 80 mmHg in 10 mmHg increments
- Mean blood pressure (MBP): 9 thresholds from 20 to 100 mmHg in 10 mmHg increments

For each threshold *T*, the threshold-based duration was calculated as:

$$D_T = \sum_{i} \Delta t_i \cdot \mathbb{1}[\text{BP}_i < T]$$

where $\Delta t_i$ denotes the time interval between consecutive measurements and $\mathbb{1}[\cdot]$ is the indicator function.

**Heart rate features (11 variables).** Total duration of tachycardia for 11 thresholds from 100 to 200 bpm in 10 bpm increments, representing the total time the heart rate exceeded each threshold.

**Oxygen saturation features (9 variables).** Total duration of desaturation for 9 thresholds from 60% to 100% in 5% increments, representing the total time SpO₂ fell below each threshold.

**ST-segment depression features (5 variables).** Total duration of ST-segment depression for 5 thresholds from 1.0 to 3.0 mm in 0.5 mm increments, based on lead II recordings.

### 2.4.3 Static Intraoperative Features (9 variables)

Static intraoperative features summarize fluid and blood product management as cumulative totals over the entire surgical procedure: urine output (mL), estimated blood loss (EBL, mL), crystalloid volume (mL), colloid volume (mL), total fluid volume (mL), intraoperative pRBC transfusion (units), fresh frozen plasma (units), platelet concentrate (units), and cryoprecipitate (units).

### 2.4.4 Intraoperative Hematocrit Features (5 variables)

Intraoperative hematocrit values were extracted from laboratory records and processed as follows. For each case, Hct measurements obtained between the start and end of surgery were collected and ordered chronologically. A piecewise-linear Hct trajectory was constructed using the most recent preoperative Hct as the initial value at the time of surgical incision and the last intraoperative Hct as the terminal value at the end of surgery. The time-weighted average hematocrit (TWA-Hct) was then computed as:

$$\text{TWA-Hct} = \frac{\text{AUC}(\text{Hct curve})}{T_{\text{total}}}$$

where AUC was estimated using the trapezoidal rule over the intraoperative Hct trajectory, and $T_{\text{total}}$ denotes the total surgical duration. For cases without intraoperative Hct measurements, TWA-Hct was set equal to the preoperative Hct value.

The five Hct-derived variables are: total number of Hct measurements, number of intraoperative Hct measurements, number of preoperative Hct measurements, area under the intraoperative Hct curve (Hct × seconds), and TWA-Hct (%).

## 2.5 Data Preprocessing

### 2.5.1 Missing Data Handling

For the internal dataset, missing values in preoperative and intraoperative features were handled during the study population construction phase; cases with critical missing variables were excluded as described in Section 2.2.1. Remaining missing values were encoded as out-of-range sentinel values to preserve missingness as an informative signal for the tree-based model: variables with a non-negative domain (e.g., laboratory values, durations) were set to −1, and variables with a real-valued domain were set to −9. This approach allows tree-based algorithms to learn split rules that distinguish missing from observed values without introducing bias through mean or zero imputation.

For the external validation dataset (BMC), three variables not recorded in the external institution's EHR — crystalloid volume, colloid volume, and platelet concentrate — were encoded with the same sentinel values. Several preoperative laboratory values (PT-INR, aPTT, albumin, AST, ALT, sodium, potassium, glucose, PT) were mapped from institution-specific column names and extracted from string-formatted values when necessary. For cases without intraoperative Hct measurements, TWA-Hct and Hct AUC were imputed using the preoperative Hct value and the surgical duration. Cases without any available hematocrit data were excluded (n = 1). Remaining missing values were encoded using the same sentinel scheme.

### 2.5.2 Categorical Variable Encoding

Categorical variables were encoded as follows:
- **Sex**: Binary (female = 1, male = 0)
- **Emergency status**: Binary (emergency = 1, elective = 0)
- **Anesthesia type**: One-hot encoding into 7 binary variables (combined spinal–epidural, epidural, general, IV regional, MAC, nerve block, spinal)
- **Surgical department**: Excluded from the final feature set to improve cross-institutional generalizability

## 2.6 Model Development

### 2.6.1 Feature Set Configurations

To evaluate the independent and incremental predictive value of intraoperative information for predicting postoperative anemia, three model configurations were defined:

| Model | Feature Groups | No. of Variables |
|---|---|---|
| **Preoperative** | Demographics + Labs + Comorbidities + Anesthesia type | 43 |
| **Intraoperative** | Threshold-based vital sign durations + Static intraop + Hct features | 64 |
| **Combined** | Preoperative + Intraoperative (all features) | 107 |

In addition, a **Threshold-only** model (50 variables: threshold-based vital sign duration features only, excluding static intraoperative features and hematocrit trajectory) was trained as an ablation study to isolate the independent predictive contribution of cumulative vital sign duration features.

### 2.6.2 Data Splitting Strategy

Temporal splitting was employed for the internal dataset to simulate a prospective validation scenario. Cases from 2016–2018 served as the development set, and cases from 2019 formed the held-out internal test set. This approach avoids data leakage from temporally subsequent cases and reflects the intended clinical deployment setting.

The external validation dataset (BMC) was used solely for evaluation without any model retraining, providing an independent assessment of cross-institutional generalizability.

### 2.6.3 Algorithm and Training Procedure

All models were trained using the CatBoost gradient boosting classifier (CatBoostClassifier; iterations = 500, depth = 4, learning rate = 0.05). CatBoost was selected based on a comprehensive model comparison of 33 classifier configurations (see Supplementary Table S1), in which it achieved the highest internal AUROC on the combined feature set. CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features with reduced overfitting.

Model training was conducted using repeated stratified 5-fold cross-validation on the development set (2016–2018), repeated 10 times with different random seeds (random_state = 0 through 9). In each fold, the training partition was further split into a training subset (80%) and a validation subset (20%) using stratified shuffle splitting to preserve the class distribution. Each of the resulting 50 fold models (10 repetitions × 5 folds) was evaluated on the held-out internal test set (2019) and the external validation set (BMC). Predictions were aggregated by averaging the predicted probabilities across all 50 fold models (ensemble mean) for final evaluation.

### 2.6.4 Model Comparison

To confirm the algorithm selection and assess whether the feature-set findings were algorithm-dependent, a comprehensive comparison of 33 classifier configurations — including logistic regression (L1, L2, ElasticNet), Gaussian Naive Bayes, k-nearest neighbors, support vector machines, decision trees, random forests, Extra Trees, bagging, AdaBoost, gradient boosting (sklearn GBM), XGBoost, XGBoost Random Forest, LightGBM, and CatBoost with varying hyperparameters — was conducted using repeated stratified 5-fold cross-validation (3 iterations) on the development set. Each model was evaluated with all three feature-set configurations, and both internal and external metrics were recorded (Supplementary Table S1). CatBoost (500 iterations, depth = 4, learning rate = 0.05) achieved the highest mean internal AUROC (0.909) and the consistent discriminative ordering of feature sets (Combined > Intraoperative > Preoperative) was replicated across all gradient boosting algorithms.

## 2.7 Statistical Analysis

### 2.7.1 Discrimination Metrics

Model discrimination was assessed using the area under the receiver operating characteristic curve (AUROC) and the area under the precision–recall curve (AUPRC). Calibration was assessed using the Brier score and calibration plots. For all metrics, bootstrap 95% confidence intervals were computed with 2,000 resampling iterations.

### 2.7.2 Model Comparison Tests

Pairwise comparisons of AUROC between models were performed using the DeLong test, a non-parametric method based on structural placement values that accounts for the correlation between AUROCs derived from the same dataset. All three pairwise comparisons were conducted: Preoperative vs. Intraoperative, Preoperative vs. Combined, and Intraoperative vs. Combined. The last comparison was specifically included to assess the incremental discriminative value of preoperative features when intraoperative data are available. Statistical significance was defined at α = 0.05 (two-sided).

### 2.7.3 Classification Performance at Optimal Threshold

For each model, the optimal classification threshold was determined by maximizing the Youden index (sensitivity + specificity − 1) on the ROC curve. At this threshold, sensitivity, specificity, positive predictive value (PPV), negative predictive value (NPV), F1 score, and accuracy were reported.

### 2.7.4 Feature Importance

Feature importance was quantified using SHapley Additive exPlanations (SHAP) values, computed via TreeSHAP on the held-out internal test set. Mean absolute SHAP values were reported for the top 10 features in each model. SHAP summary plots were generated to visualize the direction and magnitude of each feature's contribution.

### 2.7.5 Baseline Characteristics

Baseline characteristics were compared between the pooled internal cohort (SNUH, N = 35,915) and the external cohort (BMC, N = 579). Continuous variables were expressed as mean ± standard deviation and compared using the Mann–Whitney U test. Binary variables were expressed as n (%) and compared using the chi-squared test or Fisher's exact test when expected cell counts were below 5. Categorical variables with more than two levels (ASA-PS, anesthesia type) were compared using the chi-squared test.

### 2.7.6 Software

All analyses were performed in Python 3. Key libraries included scikit-learn (model training, cross-validation, evaluation metrics), CatBoost (CatBoostClassifier), SHAP (feature importance), SciPy (statistical tests), and Matplotlib (visualization). The complete analysis code is available in the project repository.

---

# 3. Results

## 3.1 Study Population

After applying the exclusion criteria described in Section 2.2, 35,915 cases constituted the final internal cohort (SNUH), temporally split into a development set (2016–2018; N = 21,233; 878 events, 4.1%) and a held-out test set (2019; N = 14,682; 596 events, 4.1%). The external cohort (BMC) comprised 579 cases (80 events, 13.8%). The detailed patient selection process is illustrated in **Figure 1**.

> **Figure 1. Study Population Flow Diagram.**
> CONSORT-style flow diagram illustrating the sequential exclusion criteria and final cohort sizes for the internal (SNUH) and external (BMC) datasets.

## 3.2 Baseline Characteristics

Demographic and clinical characteristics of the three cohorts are summarized in **Table 1**. The development and internal test sets were comparable across all variables. The external cohort (BMC) differed from the internal cohort (SNUH) in postoperative anemia prevalence (13.8% vs. 4.1%) and fluid management recording practices (crystalloid, colloid, and platelet volumes were not recorded at BMC and set to zero).

> **Table 1. Baseline Characteristics of the Study Population.**
> Demographic, clinical, and intraoperative characteristics stratified by cohort: development set (SNUH, 2016–2018; N = 21,233), internal test set (SNUH, 2019; N = 14,682), and external validation set (BMC; N = 579). Continuous variables are expressed as mean ± SD; categorical variables as n (%). The p-value column compares pooled SNUH (N = 35,915) vs. BMC (N = 579) using the Mann–Whitney U test (continuous) or chi-squared / Fisher's exact test (categorical/binary).

## 3.3 Model Performance

### 3.3.1 Internal Validation

On the held-out internal test set (N = 14,682), the Combined model achieved the highest AUROC of 0.894 (95% CI: 0.882–0.906), followed by the Intraoperative model (0.880; 0.867–0.893) and the Preoperative model (0.775; 0.755–0.794). DeLong tests confirmed that both the Intraoperative model (ΔAUROC = +0.105, p = 2.08 × 10⁻²⁴) and the Combined model (ΔAUROC = +0.119, p = 7.95 × 10⁻³⁹) significantly outperformed the Preoperative model. Detailed metrics are presented in **Table 2**.

### 3.3.2 External Validation

On the external validation set (BMC, N = 579), all three models maintained strong discrimination. The Combined model achieved the highest external AUROC of 0.882 (0.845–0.913), followed by the Intraoperative model (0.877; 0.834–0.914) and the Preoperative model (0.767; 0.704–0.823; DeLong p = 0.0028 for Intraoperative vs. Preoperative, p = 1.00 × 10⁻⁴ for Combined vs. Preoperative). The internal-to-external AUROC differences were small across all models: Preoperative Δ = −0.008, Intraoperative Δ = −0.004, Combined Δ = −0.012. ROC and precision–recall curves are shown in **Figure 2**.

### 3.3.3 Incremental Value of Preoperative Features

To assess whether preoperative variables provide incremental discriminative value beyond intraoperative features, pairwise DeLong tests were performed between the Intraoperative and Combined models. Internally, the Combined model achieved a statistically significantly higher AUROC than the Intraoperative model (0.894 vs. 0.880, ΔAUROC = +0.014, DeLong p = 2.32 × 10⁻⁸). However, externally, the Combined model only marginally outperformed the Intraoperative model (0.882 vs. 0.877, ΔAUROC = +0.006), and this difference was not statistically significant (DeLong p = 0.626). These results indicate that while preoperative features provide a small but statistically detectable incremental benefit in the internal dataset, this advantage does not generalize to an independent external population. The pairwise DeLong test results are summarized in **Table 3**.

### 3.3.4 Calibration

Calibration plots (**Figure 3**) were generated on the internal test set using 10 equally spaced probability bins to assess the agreement between predicted probabilities and observed event frequencies. The Combined model demonstrated the best calibration among the three models: its calibration curve tracked the diagonal line of perfect calibration most closely across the full probability range (predicted probabilities up to 0.98), with observed event frequencies closely matching predicted values at each bin. The Intraoperative model also showed good calibration over a wide range (up to 0.87), though with moderate deviations from the diagonal in the mid-probability range (0.3–0.6). The Preoperative model, by contrast, yielded predicted probabilities confined below 0.57 (99th percentile: 0.27), reflecting the inherent difficulty of predicting postoperative transfusion from preoperative variables alone when the event prevalence is low (4.1%). Notably, only the Combined model assigned high predicted probabilities (> 0.8) to the highest-risk patients, with corresponding observed event rates approaching 100%, indicating that the integration of both preoperative and intraoperative features enables the most reliable individual-level risk estimation across the entire risk spectrum.

> **Table 2. Discrimination and Calibration Performance of the Three Models.**
> AUROC, AUPRC, and Brier score with bootstrap 95% CI (2,000 iterations) for each model on the internal test set and external validation set. P-values are from DeLong tests using the Preoperative model as reference.

### Table 2. Model Performance Summary

| Dataset | Model | AUROC (95% CI) | AUPRC (95% CI) | Brier Score (95% CI) | ΔAUROC vs. Preop | p-value |
|---|---|---|---|---|---|---|
| **Internal** | Preoperative | 0.775 (0.755–0.794) | 0.152 (0.129–0.176) | 0.037 (0.034–0.039) | — | — |
| | Intraoperative | 0.880 (0.867–0.893) | 0.273 (0.239–0.308) | 0.033 (0.031–0.036) | +0.105 | 2.08 × 10⁻²⁴ |
| | Combined | 0.894 (0.882–0.906) | 0.297 (0.261–0.334) | 0.033 (0.030–0.035) | +0.119 | 7.95 × 10⁻³⁹ |
| **External** | Preoperative | 0.767 (0.704–0.823) | 0.378 (0.275–0.482) | 0.111 (0.090–0.133) | — | — |
| | Intraoperative | 0.877 (0.834–0.914) | 0.516 (0.410–0.629) | 0.097 (0.080–0.116) | +0.110 | 0.0028 |
| | Combined | 0.882 (0.845–0.913) | 0.500 (0.391–0.612) | 0.100 (0.081–0.119) | +0.115 | 1.00 × 10⁻⁴ |

> **Table 3. Pairwise DeLong Test Results.**
> Pairwise AUROC comparisons using DeLong's method for both internal and external datasets. All three model pairs are included: Preoperative vs. Intraoperative, Preoperative vs. Combined, and Intraoperative vs. Combined.

### Table 3. Pairwise DeLong Test Results

| Dataset | Comparison | AUROC A | AUROC B | ΔAUROC | z | p-value | Significant |
|---|---|---|---|---|---|---|---|
| **Internal** | Preop vs. Intraop | 0.775 | 0.880 | +0.105 | −10.20 | 2.08 × 10⁻²⁴ | Yes |
| | Preop vs. Combined | 0.775 | 0.894 | +0.119 | −13.03 | 7.95 × 10⁻³⁹ | Yes |
| | Intraop vs. Combined | 0.880 | 0.894 | +0.014 | −5.59 | 2.32 × 10⁻⁸ | Yes |
| **External** | Preop vs. Intraop | 0.767 | 0.877 | +0.110 | −2.98 | 0.0028 | Yes |
| | Preop vs. Combined | 0.767 | 0.882 | +0.115 | −3.85 | 1.00 × 10⁻⁴ | Yes |
| | Intraop vs. Combined | 0.877 | 0.882 | +0.006 | −0.49 | 0.626 | No |

> **Figure 2. Receiver Operating Characteristic (ROC) and Precision–Recall (PR) Curves.**
> **(A, B)** ROC curves for internal (left) and external (right) datasets. The diagonal dashed line indicates chance level (AUROC = 0.5). **(C, D)** Precision–recall curves. The horizontal dashed line indicates baseline prevalence (internal: 4.1%; external: 13.8%). AUROC and AUPRC values are shown in parentheses in each legend.

> **Figure 3. Calibration Plot.**
> Calibration curves for the four models on the internal test set (N = 14,682), generated using 10 equally spaced bins. The dashed diagonal line represents perfect calibration. The Combined model (red) tracks the diagonal most closely across the full probability range (0–1.0), demonstrating the best agreement between predicted and observed event frequencies. The Intraoperative model (orange) shows good calibration up to ~0.7 predicted probability but with moderate oscillation in the mid-range. The Threshold-only model (green) and Preoperative model (blue) both terminate below 0.6 predicted probability, reflecting the limited ability of these feature sets to identify high-risk patients in a low-prevalence setting.

## 3.4 Ablation Study: Threshold-Based Features Only

To isolate the independent predictive contribution of cumulative vital sign duration features, a Threshold-only model was trained using only the 50 threshold-based vital sign duration features (excluding TWA-Hct, EBL, and all static intraoperative features). Internally, the Threshold-only model achieved an AUROC of 0.772 (0.753–0.789), which was not significantly different from the Preoperative model (0.775; DeLong p = 0.789). Externally, the Threshold-only model achieved an AUROC of 0.755 (0.696–0.811), again comparable to the Preoperative model (0.767; DeLong p = 0.810). However, the Threshold-only model was significantly inferior to the full Intraoperative model in both datasets (internal: ΔAUROC = −0.109, p = 1.69 × 10⁻⁴¹; external: ΔAUROC = −0.121, p = 1.46 × 10⁻⁵).

These results demonstrate that threshold-based vital sign durations alone provide discrimination comparable to preoperative features but are insufficient to match the full Intraoperative model. The performance gap of approximately 11 AUROC points internally confirms that TWA-Hct and estimated blood loss are the primary drivers of the Intraoperative model's superiority, with threshold-based vital sign features serving a complementary role.

## 3.5 Feature Importance (SHAP Analysis)

SHAP (SHapley Additive exPlanations) values were computed for each model to identify the features contributing most to predictions. The top 10 features by mean absolute SHAP value for each model are shown in **Figure 4**.

In the **Preoperative model**, preoperative hemoglobin (mean |SHAP| = 0.250) and hematocrit (0.167) were the dominant predictors of postoperative anemia, followed by albumin (0.139), eGFR (0.119), and PT-INR (0.094).

In the **Intraoperative model**, TWA-Hct (0.738) and estimated blood loss (0.341) were by far the most influential features. Urine output (0.138), Hct AUC (0.089), and total fluid volume (0.088) followed. Among the threshold-based vital sign duration features, hypotension durations (MBP < 70 mmHg: 0.071) and hypoxemia durations (SpO₂ < 75%: 0.068) were notable contributors.

In the **Combined model**, TWA-Hct (0.400) and estimated blood loss (0.350) remained the two most important features. Preoperative Hb ranked third (0.169), followed by preoperative Hct (0.130) and total fluid volume (0.125), indicating that baseline hematologic status provides additional but secondary information when intraoperative data are available.

> **Figure 4. SHAP Feature Importance.**
> Mean absolute SHAP values (bar plots) for the top 10 features in each model: **(A)** Preoperative, **(B)** Intraoperative, and **(C)** Combined. SHAP values were computed using TreeSHAP on the internal test set. Higher values indicate greater contribution to the model's predictions. TWA-Hct, time-weighted average hematocrit; EBL, estimated blood loss; SBP, systolic blood pressure; SpO₂, peripheral oxygen saturation.

---

# 4. Discussion

## 4.1 Principal Findings

This study compared three feature-set configurations — Preoperative, Intraoperative, and Combined — for predicting postoperative anemia requiring transfusion within 48 hours. The central finding is that the Intraoperative model, using only threshold-based vital sign duration features, static intraoperative features, and hematocrit trajectory without any preoperative variables, achieved discrimination comparable to the Combined model (AUROC: 0.880 vs. 0.894 internally, 0.877 vs. 0.882 externally) and significantly outperformed the Preoperative model by approximately 11 AUROC points (DeLong p = 2.08 × 10⁻²⁴ internally, p = 0.0028 externally).

A critical additional finding concerns the incremental value of preoperative features. While the Combined model marginally outperformed the Intraoperative model internally (ΔAUROC = +0.014, DeLong p = 2.32 × 10⁻⁸), this small improvement did not transfer to the external cohort, where the difference was not statistically significant (AUROC 0.882 vs. 0.877, ΔAUROC = +0.006, DeLong p = 0.626). This pattern — a statistically significant but clinically marginal internal advantage that does not reach significance externally — suggests that the 43 preoperative features contribute minimally to discrimination when intraoperative monitoring data are already available.

However, the two models diverge when evaluated on calibration rather than discrimination. The calibration plot (Figure 3) reveals that the Combined model produced predicted probabilities most closely tracking the diagonal line of perfect calibration, spanning the full 0-to-1.0 range with observed event rates approaching 100% among the highest-risk patients. By contrast, the Intraoperative model showed moderate deviations from perfect calibration in the mid-probability range, and the Preoperative model was confined to predicted probabilities below 0.6. This distinction suggests that while intraoperative features drive discrimination, the addition of preoperative variables improves the reliability of individual-level probability estimates — a property that is clinically relevant for risk communication and threshold-based decision-making.

## 4.2 Feature Importance and Clinical Interpretation

SHAP analysis (Figure 4) provides insight into the mechanisms underlying each model's predictions.

The Preoperative model relied predominantly on baseline hematologic status — preoperative Hb and Hct together accounted for the largest share of predictive importance. These are well-established clinical risk factors for postoperative anemia, yet they yielded only moderate discrimination (AUROC ~0.78), confirming that baseline patient status alone is insufficient.

In the Intraoperative and Combined models, TWA-Hct and estimated blood loss emerged as the two dominant features, with substantially higher SHAP values than all other predictors (Intraoperative: TWA-Hct 0.738, EBL 0.341). This indicates that the hematocrit trajectory during surgery and cumulative surgical bleeding jointly capture the primary risk signal. Notably, when preoperative Hb was available in the Combined model, it ranked third (SHAP 0.169) — still contributing but secondary to intraoperative dynamics. This hierarchy supports the interpretation that intraoperative physiological changes supersede baseline status for predicting postoperative anemia.

Among the threshold-based vital sign duration features, hypotension durations (MBP < 70 mmHg: SHAP 0.071) and hypoxemia durations (SpO₂ < 75%: SHAP 0.068 in the Intraoperative model) appeared in the top features. While individually their SHAP contributions were modest compared to TWA-Hct and EBL, the collective contribution of the 50 threshold-based features represents a substantial share of the Intraoperative model's predictive power. The ablation study (Section 3.4) quantifies this: the Threshold-only model — using only these 50 vital sign duration features — achieved an AUROC of 0.772 internally and 0.755 externally, comparable to the Preoperative model. This confirms that cumulative vital sign derangement durations capture clinically meaningful risk information, but that TWA-Hct and EBL are indispensable for achieving the full Intraoperative model's performance (ΔAUROC ≈ 0.11 gap internally).

## 4.3 Generalizability of Intraoperative Features

All three models demonstrated robust generalization, with internal-to-external AUROC gaps ranging from −0.004 to −0.012. Among the three, the Intraoperative model exhibited the smallest gap (Δ = −0.004), followed by the Preoperative model (Δ = −0.008) and the Combined model (Δ = −0.012). While these differences in generalizability are numerically small and should be interpreted cautiously given overlapping confidence intervals, the consistent pattern supports the inference that intraoperative features maintain stable cross-institutional performance.

This stability can be understood through the nature of the features:

| Feature type | Reflects | Generalizability |
|---|---|---|
| TWA-Hct (trajectory) | Patient's hematocrit dynamics during surgery | High — derived from standardized laboratory measurements |
| Threshold-based vital sign durations (BP, HR, SpO₂) | Patient physiological state | High — physiology is institution-independent |
| Static intraop (crystalloid, colloid, platelet volumes) | Clinical practice patterns | Low — recording practices and protocols vary across institutions |
| Static intraop (EBL, intraop RBC) | Mix of physiology and practice | Moderate — estimation methods and transfusion triggers differ |

At BMC, three static intraoperative variables (crystalloid, colloid, platelet volumes) were not recorded and were set to zero. Despite this data limitation, the Intraoperative model maintained strong performance (AUROC 0.877), indicating that the threshold-based vital sign duration features and hematocrit trajectory carry sufficient predictive information for postoperative anemia independent of fluid balance documentation.

This observation aligns with the concept of "hypotension burden" in the anesthesia literature: threshold-based duration below physiological cutoffs captures the dose of hemodynamic insult more faithfully than summary statistics (mean, min, max), and this dose is determined by the patient's physiology rather than by local clinical conventions.

## 4.4 Ablation Study: Role of Threshold-Based Vital Sign Features

To disentangle the contributions of different intraoperative feature groups, an ablation analysis was conducted using a Threshold-only model (50 threshold-based vital sign duration features only, excluding TWA-Hct, EBL, and all static intraoperative features). The Threshold-only model achieved an AUROC of 0.772 internally and 0.755 externally — comparable to the Preoperative model (internal 0.775, DeLong p = 0.789; external 0.767, DeLong p = 0.810) but significantly lower than the full Intraoperative model (internal ΔAUROC = −0.109, p = 1.69 × 10⁻⁴¹; external ΔAUROC = −0.121, p = 1.46 × 10⁻⁵).

These findings have several implications. First, vital sign duration features alone provide meaningful discrimination, confirming that the cumulative "dose" of intraoperative hemodynamic derangement captures real pathophysiological risk. Second, the ~11-point AUROC gap between the Threshold-only and full Intraoperative models identifies TWA-Hct and EBL as the critical features that elevate the Intraoperative model to the 0.88 AUROC range. Third, the small generalization gap of the Threshold-only model (internal 0.772, external 0.755; Δ ≈ −0.017) supports the argument that physiology-based features are inherently institution-independent.

From a practical standpoint, this suggests that even in settings where intraoperative laboratory values (Hct) and estimated blood loss are not reliably documented, continuous vital sign monitoring alone can provide prediction accuracy comparable to preoperative models — a finding relevant for resource-limited surgical environments.

## 4.5 Calibration and Brier Score Interpretation

Calibration was assessed using Brier scores and calibration plots (Figure 3). While Brier scores were numerically similar across models (internal: Preoperative 0.037, Intraoperative 0.033, Combined 0.033), these aggregate metrics mask an important qualitative difference revealed by the calibration plot. The Combined model produced the best-calibrated predictions: its calibration curve tracked the diagonal of perfect calibration most faithfully, and it was the only model to assign high predicted probabilities (> 0.8) to the highest-risk patients, with corresponding observed event rates near 100%. The Intraoperative model showed good calibration over most of its range but exhibited oscillations in the mid-probability bins (0.3–0.6), while the Preoperative model's predictions were compressed below 0.6.

This calibration advantage of the Combined model is clinically meaningful. A well-calibrated model produces predicted probabilities that directly approximate the true event rate — a predicted probability of 0.7 corresponds to approximately 70% observed transfusion. This property enables clinicians to interpret model outputs as reliable risk estimates for individual patients, facilitating shared decision-making and evidence-based threshold selection. Brier score alone does not capture this distinction, because in low-prevalence settings (4.1%), models that assign near-zero probabilities to most patients achieve Brier scores approaching the theoretical floor (≈ 0.039) regardless of their calibration quality for high-risk patients.

## 4.6 AUPRC and Prevalence Considerations

The higher absolute AUPRC values in the external dataset (Intraoperative: 0.516 vs. 0.273 internally) reflect the substantially higher event prevalence at BMC (13.8% vs. 4.1%), which shifts the precision–recall baseline upward. AUPRC is prevalence-dependent and should not be compared across datasets with different event rates. The consistent discriminative ordering of models (Intraoperative ≈ Combined > Preoperative) across both prevalence settings reinforces the robustness of the findings.

The difference in prevalence between the two institutions (4.1% vs. 13.8%) itself warrants discussion. This may reflect differences in transfusion triggers, patient case-mix severity, surgical case types, or institutional transfusion protocols rather than a true difference in postoperative anemia incidence. The fact that model discrimination was maintained despite this substantial prevalence shift provides evidence for the models' robustness to population-level variation.

## 4.7 Clinical Implications

From a clinical deployment perspective, the strong discrimination and robust calibration of the Intraoperative and Combined models support several concrete use cases. Importantly, the choice between models depends on the clinical objective:

1. **Post-anesthesia care unit (PACU) screening.** For binary high-risk vs. low-risk classification at the conclusion of surgery, the Intraoperative model provides sufficient discrimination (AUROC 0.880) using only data already captured during the operation, without requiring access to preoperative records. Patients flagged as high-risk can be prioritized for early postoperative hemoglobin checks.

2. **Individual risk communication.** When clinicians need to communicate a specific probability of transfusion to patients or care teams, the Combined model is preferred owing to its superior calibration — its predicted probabilities most closely approximate true event rates across the full risk spectrum (Figure 3). This enables statements such as "this patient has an estimated 70% probability of requiring transfusion within 48 hours" with greater reliability.

3. **Alert threshold calibration.** The optimal alert threshold can be calibrated to institutional preferences based on the desired trade-off between sensitivity and specificity, balancing early detection against alert fatigue. The Combined model's well-calibrated probabilities facilitate principled threshold selection.

4. **Blood bank resource planning.** Aggregate risk scores across a day's surgical schedule could inform blood bank preparation, enabling proactive cross-matching for patients at elevated risk while avoiding unnecessary preparation for low-risk cases.

In patients already manifesting severe anemia or massive intraoperative bleeding, clinical judgment alone suffices, and the model's role shifts from prediction to risk quantification.

## 4.8 Limitations

Several limitations should be considered.

First, this is a retrospective study, and the temporal split (2016–2018 development, 2019 test) provides only a pseudo-prospective evaluation. Prospective validation in a real-time clinical workflow is needed to assess practical utility and potential alert fatigue.

Second, the external validation cohort (BMC, N = 579) is relatively small, resulting in wider confidence intervals for external performance estimates. Bootstrap 95% CIs were reported to quantify this uncertainty.

Third, three intraoperative variables (crystalloid, colloid, platelet volumes) were not recorded at BMC and were set to zero. While this did not substantially impair the Intraoperative model's performance, it represents a systematic difference between institutions that should be addressed in future multi-center studies with harmonized data collection.

Fourth, this study used a single primary machine learning algorithm (CatBoost), selected based on a comprehensive comparison of 33 classifier configurations (Supplementary Table S1). Although this comparison confirmed that the feature-set findings were consistent across gradient boosting algorithms, future work should assess whether the findings hold with fundamentally different model architectures (e.g., neural networks, time-series models).

Fifth, postoperative anemia was operationally defined as any pRBC transfusion within 48 hours, which conflates the clinical endpoint of anemia with the treatment decision of transfusion. This definition does not capture anemic patients managed conservatively without transfusion, nor does it differentiate between clinically appropriate and potentially avoidable transfusions. Furthermore, transfusion triggers may vary across institutions and clinicians, meaning the outcome itself may partly reflect local clinical practice rather than a purely physiological state. The substantially higher event rate at BMC (13.8% vs. 4.1%) may partially reflect such differences. Future studies could incorporate hemoglobin-based criteria or clinical appropriateness assessments for a more comprehensive definition.

Sixth, the model predicts postoperative anemia risk at the end of surgery. A clinically ideal system would provide dynamic, continuously updated risk estimates throughout the surgical procedure. Extending the model to support real-time intraoperative prediction at multiple time points is an important direction for future work.

## 4.9 Conclusions

Using CatBoost gradient boosting as the primary algorithm, this study demonstrates that intraoperative features — particularly time-weighted average hematocrit, estimated blood loss, and threshold-based vital sign duration features — provide strong, independently sufficient, and robustly generalizable prediction of postoperative anemia requiring transfusion. The addition of preoperative variables yields minimal incremental benefit in discrimination when intraoperative monitoring data are available (ΔAUROC = +0.014 internally, +0.006 externally [not significant]), but produces the best-calibrated predictions, with the Combined model's probability estimates most closely approximating true event rates across the full risk spectrum. Ablation analysis confirms that while threshold-based vital sign duration features alone provide discrimination comparable to preoperative features, the combination with TWA-Hct and EBL is essential for achieving the full Intraoperative model's superior performance. These intraoperative features capture patient physiological state rather than institution-specific clinical practices, explaining their stable cross-institutional performance. The findings support the integration of real-time intraoperative monitoring data into postoperative anemia risk prediction systems, with the Combined model recommended when well-calibrated probability estimates are needed for clinical decision-making.

---

# References

*(To be added)*
