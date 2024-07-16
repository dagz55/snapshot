import pandas as pd

# Data extracted from the image
data = {
    "Name": ["Divin", "Suarez", "Ryun", "Balay Cuica", "Casa Yana", "Jace", "Ola", "Charlie"],
    "Price 1": [2100, 2100, 2100, 17400, 18000, 1100, 1100, 1100],
    "Price 2": [2200, 2200, 2200, 1900, 2000, 1200, 1200, 1200],
    "Total Price": [4300, 4300, 4300, 19300, 20000, 2300, 2300, 2300],
    "Notes": ["good for 4pax", "good for 4pax", "good for 4pax", None, "good for 4pax", "good for 2pax", None, None]
}

# Creating a DataFrame
df = pd.DataFrame(data)

# Displaying the DataFrame to the user
import ace_tools as tools; tools.display_dataframe_to_user(name="Travel Costs", dataframe=df)

df
