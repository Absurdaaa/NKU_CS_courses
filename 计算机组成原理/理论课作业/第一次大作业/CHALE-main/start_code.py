import json
import numpy as np
import pandas as pd


###########  Step 1: Load synthetic hallucinated dataset  ###########
    # follow ./synthetic_halu_data_simplified.ipynb
    # with open('../hallucinated_ans.json', 'r') as f:
with open('hallucinated_ans_final_filtered.json', 'r') as f:
    loaded_hallucinated_ans = json.load(f)
    
# The dataset includes following keys
print(loaded_hallucinated_ans.keys())

# print(loaded_hallucinated_ans)


# df = pd.json_normalize(loaded_hallucinated_ans)
# df.to_csv('hallucinated_answers.csv', index=False)

import pandas as pd

# Assuming loaded_hallucinated_ans is the dictionary you provided
# Convert the dictionary to a DataFrame
df = pd.DataFrame(loaded_hallucinated_ans)

# # Transpose the DataFrame so each list becomes a row
# #df_transposed = df.transpose()

# # Save the transposed DataFrame to a CSV file
# df.to_csv('hallucinated_answers.csv', index=False)

# print("Data saved as 'hallucinated_answers.csv'")

print(df.size)