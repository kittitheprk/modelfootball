import pandas as pd
import os

filename = 'prediction_tracker.xlsx'

if os.path.exists(filename):
    df = pd.read_excel(filename, sheet_name='Predictions')
    
    # Calculate Summary again
    verified = df[df['Actual_Result'].notna() & (df['Actual_Result'] != '')].copy()
    total_verified = len(verified)
    
    if total_verified > 0:
        result_correct = verified['Result_Correct'].sum()
        score_correct = verified['Score_Correct'].sum()
        result_accuracy = (result_correct / total_verified) * 100
        score_accuracy = (score_correct / total_verified) * 100
        avg_gd_error = verified['Goal_Diff_Error'].mean()
    else:
        result_correct = 0
        score_correct = 0
        result_accuracy = 0
        score_accuracy = 0
        avg_gd_error = 0
        
    summary_data = {
        'Metric': [
            'Total Predictions',
            'Results Verified',
            'Result Accuracy (%)',
            'Exact Score Accuracy (%)',
            'Avg Goal Diff Error',
            'Home Win Predictions',
            'Draw Predictions',
            'Away Win Predictions',
            'Correct Predictions',
            'Incorrect Predictions'
        ],
        'Value': [
            len(df),
            total_verified,
            f"{result_accuracy:.1f}%",
            f"{score_accuracy:.1f}%",
            f"{avg_gd_error:.2f}",
            len(df[df['Pred_Result'] == 'Home']),
            len(df[df['Pred_Result'] == 'Draw']),
            len(df[df['Pred_Result'] == 'Away']),
            int(result_correct),
            int(total_verified - result_correct)
        ]
    }
    summary_df = pd.DataFrame(summary_data)
    
    # Save both sheets
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Predictions', index=False)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
    print("Summary sheet restored successfully!")
    print(summary_df.to_string())
