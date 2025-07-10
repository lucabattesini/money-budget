import pandas as pd
import matplotlib.pyplot as plt
import os

file_path = "./db"
file = os.listdir(file_path)

if file[0].endswith(".csv"):
    print("Verified")
else: 
    raise ValueError("It isn't a csv file")

df = f"./db/{file[0]}"