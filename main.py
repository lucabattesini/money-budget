import pandas as pd
import matplotlib.pyplot as plt
import os

# Gets the csv file name inside db folder
file_path = "./db"
file = os.listdir(file_path)

# Verify if it's an csv file
if not file[0].endswith(".csv"):
    raise ValueError("It isn't a CSV file")

df = f"./db/{file[0]}"