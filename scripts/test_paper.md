# Machine Learning-Based 30-Day Readmission Prediction for Heart Failure Patients

## Abstract

This study developed a machine learning-based 30-day readmission prediction model using electronic health records from 12,000 heart failure patients. We compared five gradient boosting frameworks and evaluated their performance with AUROC, AUPRC, and calibration metrics.

## Introduction

Heart failure affects approximately 6.2 million adults in the United States, imposing a significant burden on healthcare systems. Thirty-day readmission rates remain high despite various intervention programs.

Early identification of patients at high risk of readmission could enable targeted interventions and reduce healthcare costs. Previous studies have shown that machine learning models can outperform traditional risk scores such as the LACE index in predicting readmissions.

## Methods

We evaluated five gradient boosting frameworks: XGBoost, LightGBM, CatBoost, TabNet, and a tuned random forest baseline. Among the algorithms tested, CatBoost employs ordered boosting and symmetric decision trees, offering robust handling of heterogeneous features and native categorical support. LightGBM uses histogram-based splitting for faster training, while XGBoost remains the most widely adopted in clinical prediction studies.

Feature engineering was performed using the OMOP Common Data Model to standardize clinical variables across institutions. We extracted 142 features including demographics, vital signs, laboratory values, medication history, and prior utilization patterns.

## Results

Our best-performing model achieved an AUROC of 0.78 and AUPRC of 0.45 on the held-out test set. CatBoost showed the highest discrimination among all tested frameworks. The Brier score was 0.18, indicating reasonable calibration.

Feature importance analysis revealed that the number of prior hospitalizations in the past year, serum sodium levels, and ejection fraction were the top three predictors. These findings are consistent with prior literature on heart failure readmission risk factors.

## Discussion

The superior performance of gradient boosting methods over logistic regression aligns with recent benchmarking studies in clinical prediction. However, the marginal improvement over simpler models suggests that feature engineering may be more impactful than model selection in this domain.

Our results should be interpreted with caution given the single-center study design. Multi-center validation is needed before clinical deployment, as model transportability remains a known challenge in clinical machine learning.

## Limitations

This study has several limitations. The retrospective design limits causal inference. Additionally, our dataset lacked granular social determinants of health data, which have been shown to significantly influence readmission risk. The use of a single-center dataset may limit generalizability.

## Acknowledgments

We thank the clinical informatics team for data extraction support.

## References

1. Smith et al. (2020) Heart failure statistics.
2. Chen & Guestrin (2016) XGBoost paper.
