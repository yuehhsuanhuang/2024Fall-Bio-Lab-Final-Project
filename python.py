# !pip install mne

import math
from mne.time_frequency import morlet
import numpy as np
from scipy.signal import butter, filtfilt
from scipy.signal import detrend
from scipy.stats import zscore
import serial
import time

'''
----------------------------------------------------------------------------
Setup (read file, constants, shared functions)
'''
ser = serial.Serial('COM3', 9600)

fs = 200
data = np.loadtxt("v8.txt")

eeg = data[:,0].copy()
ecg = data[:,1].copy()

duration_length = 1 * 60 * fs  # number of simples seen per loop
num_duration = len(eeg) // duration_length

def get_bound(signal, k):
    Q1 = np.percentile(signal, 25)
    Q3 = np.percentile(signal, 75)
    IQR = Q3 - Q1
    lower_bound = Q3 - k * IQR
    upper_bound = Q3 + k * IQR
    return lower_bound, upper_bound

'''
----------------------------------------------------------------------------
ECG functions and parameters
'''

v = np.linspace(0.5 * np.pi, 1.5 * np.pi, 15)
peak_filter = 2*np.sin(v)

step1_segment_length = 5 * 60 * fs
def get_r_peaks_step1(ecg_transformed):
    r_peaks = []
    num_segments = math.ceil(len(ecg_transformed) / step1_segment_length)

    for i in range(num_segments):
        start_idx = i * step1_segment_length
        end_idx = (i + 1) * step1_segment_length
        ecg_segment = ecg_transformed[start_idx:end_idx]

        # get upper bound
        _, upper_bound = get_bound(ecg_segment,3)

        # find region
        greater_than_ub = ecg_segment > upper_bound
        edges = np.diff(greater_than_ub.astype(int))
        starts = np.where(edges == 1)[0] + start_idx + 1
        ends = np.where(edges == -1)[0] + start_idx + 1

        # if > upper_bound region cross segments
        if ends[0] < starts[0]:
            starts = np.insert(starts, 0, start_idx)
        if starts[-1] > ends[-1]:
            ends = np.append(ends, end_idx-1)
        if starts[-1] == ends[-1]:
            starts = np.delete(starts, -1)
            ends = np.delete(ends, -1)

        # r_peak append local max in each > upper_bound region
        for start, end in zip(starts, ends):
            max_idx = np.argmax(ecg_transformed[start:end]) + start
            # assume only 1 peak in each 30 sec
            if len(r_peaks) == 0 or max_idx - r_peaks[-1] > 30 / 60 * fs:
                r_peaks.append(max_idx)
            if len(r_peaks) > 0 and max_idx - r_peaks[-1] <= 30 / 60 * fs and ecg_transformed[max_idx] > ecg_transformed[r_peaks[-1]]:
                r_peaks.pop()
                r_peaks.append(max_idx)
    return r_peaks

step2_segment_length = 100
n = 10
def get_r_peaks_step2(rr_):
    rr = rr_.copy()
    num_segments = math.ceil(len(rr) / step2_segment_length)

    for i in range(num_segments):
        start_idx = i * step2_segment_length
        end_idx = (i + 1) * step2_segment_length
        rr_segment = rr[start_idx:end_idx]

        outliers = np.abs(zscore(rr_segment)) > 2

        for i in np.where(outliers)[0]:
            start = max(0, i - n)
            end = min(len(rr_segment), i + n)

            neighbors = np.concatenate([rr_segment[start:i], rr_segment[i+1:end]])
            rr[i+start_idx] = np.mean(neighbors)
    return rr

def get_ecg_result(cur_ecg):
    ecg_transformed = np.correlate(cur_ecg, peak_filter, mode="same")
    r_peaks = get_r_peaks_step1(ecg_transformed)
    rr = np.diff(r_peaks)/fs  # peak per sec
    rr_post = get_r_peaks_step2(rr)
    heart_rates = rr_post*60  # bpm
    avg_hr = np.mean(heart_rates[(-1)*(duration_length):])
    sdnn = np.std(rr_post*1000,ddof=1)
    return avg_hr, sdnn

'''
----------------------------------------------------------------------------
EEG functions and parameters
'''

cf = 13
nc = 12
eeg_power_thresh = 0.08
wlt = morlet(fs, [cf], n_cycles=nc)[0]

def bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    filtered_data = filtfilt(b, a, data)
    return filtered_data

truncate_region_length = int(0.5 * fs)  # truncate 0.5 sec
def truncate_abnormal_region(cur_eeg_):
    cur_eeg = cur_eeg_.copy()
    num_segments = math.ceil(len(cur_eeg) / truncate_region_length)
    for i in range(num_segments):
        start_idx = i * truncate_region_length
        end_idx = (i + 1) * truncate_region_length
        eeg_segment = cur_eeg[start_idx:end_idx]
        difference = np.max(eeg_segment)-np.min(eeg_segment)
        if difference >= 100 or abs(np.mean(eeg_segment)) >= 30:
            cur_eeg[start_idx:end_idx] = 0
    return cur_eeg

def format_detected_time(detected_n):
    total_minutes = detected_n / fs / 60
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    return f"{hours:02}:{minutes:02}"

def  get_eeg_result(cur_eeg_):
    cur_eeg = truncate_abnormal_region(cur_eeg_.copy())
    filtered_eeg = bandpass_filter(cur_eeg,12,16,200)

    # Convolve the wavelet and extract magnitude and phase
    analytic = np.convolve(filtered_eeg, wlt, mode='same')
    magnitude = np.abs(analytic)

    # Square and normalize the magnitude from 0 to 1 (using the min and max)
    power = np.square(magnitude)
    norm_power = (power - power.min()) / (power.max() - power.min())

    # Find supra-threshold values
    supra_thresh = np.where(norm_power >= eeg_power_thresh)[0]

    # Extract start and end of each spindles
    sp = np.split(supra_thresh, np.where(np.diff(supra_thresh) != 1)[0] + 1)
    idx_start_end = np.array([[k[0], k[-1]] for k in sp])

    # Extract the duration (in ms) of each spindles
    sp_dur = (np.diff(idx_start_end, axis=1) / fs * 1000).flatten()

    # Extract the peak-to-peak amplitude and frequency
    sp_amp = np.zeros(len(sp))

    for i in range(len(sp)):
        sp_amp[i] = np.ptp(detrend(filtered_eeg[sp[i]]))

    duration = sp_dur
    amplitude = sp_amp
    candidates = []

    for i in range(len(duration)):
        if duration[i]>1000 and amplitude[i]>20:
            candidates.append(i)

    detected = "NULL"
    if len(candidates) > 0:
      detected = format_detected_time(sp[candidates[0]][0])

    return detected

'''
----------------------------------------------------------------------------
Main code (simulation)
'''
HR = []
SDNN = []
detected_spindle = False
AT = ""

print("Waiting for 'start' message...")
while True:
    if ser.in_waiting > 0:
        received_message = ser.readline().decode().strip()
        if received_message == "start":
            print("Received 'start' message. Starting loop...")
            break

print("min HR SDNN detected_spindle")
for i in range(num_duration + 1):
    start_time = time.time()
    
    end_idx = (i + 1) * duration_length
    current_eeg = eeg[:end_idx]
    current_ecg = ecg[:end_idx]

    detected = get_eeg_result(current_eeg)
    hr, sdnn = get_ecg_result(current_ecg)

    HR.append(hr)
    SDNN.append(sdnn)

    if detected != "NULL" and not detected_spindle:
        detected_spindle = True
        AT = detected
        ser.write(("d," + str(detected) + "\n").encode())
        print(f"Sent: d,{str(detected)}")

    ser.write(("b," + str(round(hr, 2)) + ","+str(round(sdnn, 2))+"\n").encode())
    print(f"{i} sec sent: b,{str(round(hr, 2))},{str(round(sdnn, 2))}")
    
    
    elapsed_time = time.time() - start_time
    if elapsed_time < 1:
        time.sleep(1 - elapsed_time)
        
ser.close()