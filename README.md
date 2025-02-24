# 2024Fall-Bio-Lab-Final-Project
2024 Fall Biomedical Engineering Final Project

This repository is the
Please refer to this demo video on YouTube for further information: https://youtu.be/zepfCfav4Hw

Note: 

This demo use v8 as the primary example (Please refer to the Dataset folder to check for v8.txt). 

To simulate the real-time scenario, we use a Python loop with time.sleep() to simulate reading EEG and ECG signals every minute, then return the asleepTime (AT) "00:15" (falling asleep at the 15th minute) to the Arduino set. The Arduino set calculates the sleep duration (SD) + asleep time (AT) = alarm time (BT). Using the DS3231 time module, it checks the time, and when BT is reached, the buzzer goes off.

The time of getting into bed (starting the measurement) in the video is "02:50", and the sleep duration (SD) set in the app is "00:10". After the measurement starts, the Python program will transmit the heart rate (HR) and the entire SDNN (standard diviation of NN intervals) to the app every minute (simulated with 1 second representing 1 minute) through the Arduino set, and display health risks and a graph showing the HR trend during sleep. Since the EEG model detects a spindle at the 15th minute, it sends this information back to the Arduino set, calculates the alarm time (BT), and the buzzer goes off when BT+SD = 15+10 minutes (at the 25-second mark in the video).


