#!/usr/bin/env python3
"""
Morse Code Eye Blink Detector
Simple eye blink detection for Morse code communication.

Author: GitHub Copilot  
Date: August 24, 2025
"""

import cv2
import numpy as np
import time
import tkinter as tk
from threading import Thread
import math
import subprocess
import os
import mediapipe as mp
from collections import deque

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.4  # Increased for reliability
    print("✅ pyautogui imported successfully")
except ImportError:
    print("⚠️ Warning: pyautogui not available. Window management modes will not work.")
    pyautogui = None

try:
    import win32gui
    import win32con
    print("✅ pywin32 imported successfully")
except ImportError:
    print("⚠️ Warning: pywin32 not available. Some window management features may be limited.")
    win32gui = None

# Common landmark indices for MediaPipe face mesh
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

def eye_aspect_ratio(landmarks, eye_idxs, frame_w, frame_h):
    def xy(i):
        lm = landmarks[i]
        return np.array([lm.x * frame_w, lm.y * frame_h])
    p1 = xy(eye_idxs[0])
    p2 = xy(eye_idxs[1])
    p3 = xy(eye_idxs[2])
    p4 = xy(eye_idxs[3])
    p5 = xy(eye_idxs[4])
    p6 = xy(eye_idxs[5])
    vert1 = np.linalg.norm(p2 - p6)
    vert2 = np.linalg.norm(p3 - p5)
    horiz = np.linalg.norm(p1 - p4)
    if horiz == 0:
        return 0.0
    ear = (vert1 + vert2) / (2.0 * horiz)
    return ear

class MorseDetector:
    def __init__(self):
        self.mp_face = mp.solutions.face_mesh
        self.face_mesh = self.mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.morse_dict = {
            '.-': 'A',      # Brave Browser
            '-.': 'B',      # Notepad 
            '..': 'C',      # WhatsApp
            '-..': 'D',     # Virtual Keyboard
            '---': 'M',     # App Switch
            '.--': 'W',     # Minimize Window
            '--.-': 'Q',    # Close Window
            '.': 'L',       # LEFT
            '-': 'R',       # RIGHT
            '..': 'I',      # UP
            '-.': 'N',      # DOWN
            '.-': 'S',      # SELECT
            '..-.': 'F',
            '--.': 'G',
            '....': 'H',
            '.---': 'J',
            '-.-': 'K',
            '...-': 'O',
            '.--.': 'P',
            '.-.': 'T',
            '..-': 'U',     # Undo
            '..--': 'V',    # Enter key
            '-..-': 'X',    # Exit keyboard mode
            '-.--': 'Y',    # Tab mode toggle
            '--..': 'Z'     # Right click
        }
        self.app_stack = []
        self.window_switch_count = 0
        self.tab_mode = False
        self.keyboard_mode = False
        self.typed_text = ''
        self.subtitle = ''
        self.subtitle_time = 0
        self.subtitle_duration = 2.0
        self.keyboard_layout = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M'],
            ['SPACE', 'ENTER', 'BACKSPACE']
        ]
        self.keyboard_row = 0
        self.keyboard_col = 0
        self.recent_blinks = []
        self.ear_history = deque(maxlen=8)
        self.currently_blinking = False
        self.blink_start_time = None
        self.last_blink_duration = 0
        self.total_blinks = 0
        self.last_blink_type = ""
        self.pattern = ""
        self.last_pattern_time = time.time()
        self.dot_threshold = 0.3
        self.dash_threshold = 0.5
        self.letter_timeout = 3.0
        self.ear_threshold = 0.22
        self.startup_countdown_duration = 10.0
        self.startup_time = time.time()
        self.system_active = False
        print("✅ Morse Code Detector Initialized!")
        print("📋 Instructions:")
        print("   • Quick blink (<0.3s) = DOT")
        print("   • Long blink (>0.4s) = DASH")
        print("   • 3 second pause = Complete letter")
        print("   • Face the light source for best results")
        print("🚀 Applications:")
        print("   • A (.-): Brave Browser")
        print("   • B (-.): Notepad")
        print("   • C (..): WhatsApp")
        print("   • D (-..): Virtual Keyboard + Navigation Mode")
        print("🔧 Mode Commands:")
        print("   • Y (-.--): Toggle Tab Mode")
        print("   • U (..-): Undo (close last app)")
        print("   • V (..--): Enter Key (UNIVERSAL)")
        print("⌨️ Virtual Keyboard Navigation:")
        print("   • I (..): Move Up")
        print("   • N (-.): Move Down")
        print("   • L (.): Move Left")
        print("   • R (-): Move Right")
        print("   • S (.-): Select Key")
        print("   • X (-..-): Exit Navigation Mode & Close OSK")
        print("⚡ Quick Actions:")
        print("   • M (---): Progressive App Switch")
        print("   • E (.): Left Click / Select Key")
        print("   • Z (--..): Right Click")
        print("🪟 Window Management:")
        print("   • W (.--): Minimize Current Window")
        print("   • Q (--.-): Close Current Window (Alt+F4)")
        print("🗂️ Tab Mode (when active):")
        print("   • A: Next Element (Tab) | B: Previous Element (Shift+Tab)")
        print("🎯 System will start after 10-second countdown!")

    def show_pattern_subtitle(self):
        if self.pattern:
            def _show_middle_pattern():
                try:
                    root = tk.Tk()
                    root.overrideredirect(True)
                    root.attributes("-topmost", True)
                    root.attributes("-alpha", 0.7)
                    root.configure(bg='black')
                    screen_width = root.winfo_screenwidth()
                    screen_height = root.winfo_screenheight()
                    width, height = 300, 100
                    x = (screen_width - width) // 2
                    y = (screen_height - height) // 2
                    root.geometry(f"{width}x{height}+{x}+{y}")
                    label = tk.Label(root, text=f"Pattern: {self.pattern}",
                                   font=("Helvetica", 24), fg="white", bg="black")
                    label.pack(expand=True)
                    root.after(2000, root.destroy)
                    root.mainloop()
                except Exception as e:
                    print(f"[PATTERN MIDDLE] Error: {e}")
            Thread(target=_show_middle_pattern, daemon=True).start()

    def show_pattern_overlay(self, pattern_text):
        def _show_top_pattern():
            try:
                root = tk.Tk()
                root.overrideredirect(True)
                root.attributes("-topmost", True)
                root.attributes("-alpha", 0.7)
                root.configure(bg='navy')
                screen_width = root.winfo_screenwidth()
                width, height = 400, 60
                x = (screen_width - width) // 2
                y = 10
                root.geometry(f"{width}x{height}+{x}+{y}")
                label = tk.Label(root, text=f"Pattern: {pattern_text}",
                               font=("Helvetica", 20), fg="white", bg="navy")
                label.pack(expand=True)
                root.after(2000, root.destroy)
                root.mainloop()
            except Exception as e:
                print(f"[PATTERN TOP] Error: {e}")
        Thread(target=_show_top_pattern, daemon=True).start()

    def draw_immediate_subtitle(self, frame):
        current_time = time.time()
        if self.subtitle and current_time - self.subtitle_time < self.subtitle_duration:
            height, width = frame.shape[:2]
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.2
            thickness = 3
            padding = 10
            (text_width, text_height), baseline = cv2.getTextSize(
                self.subtitle, font, font_scale, thickness)
            x = (width - text_width) // 2
            y = height - 60
            bg_x1 = x - padding
            bg_y1 = y - text_height - padding
            bg_x2 = x + text_width + padding
            bg_y2 = y + baseline + padding
            overlay = frame.copy()
            cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            cv2.putText(frame, self.subtitle, (x, y),
                       font, font_scale, (0, 255, 0), thickness, cv2.LINE_AA)
            cv2.putText(frame, self.subtitle, (x, y),
                       font, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

    def check_complete_letter(self):
        if not self.system_active or not self.pattern:
            return
        current_time = time.time()
        if current_time - self.last_pattern_time > self.letter_timeout:
            letter = self.resolve_context_letter(self.pattern)
            if letter:
                print(f"📝 Morse pattern: {self.pattern}")
                print(f"🎉 Detected letter: {letter}")
                self.show_letter_popup(letter)
            else:
                print(f"❓ Unknown pattern: '{self.pattern}'")
                self.subtitle = f"❓ Unknown Pattern: {self.pattern}"
                self.subtitle_time = time.time()
            self.pattern = ""

    def show_current_key(self):
        if (self.keyboard_row < len(self.keyboard_layout) and
            self.keyboard_col < len(self.keyboard_layout[self.keyboard_row])):
            current_key = self.keyboard_layout[self.keyboard_row][self.keyboard_col]
            self.create_key_indicator(current_key)
            self.highlight_osk_key(current_key)
            print(f"[KEYBOARD NAV] Current key: {current_key} at position ({self.keyboard_row}, {self.keyboard_col})")

    def create_key_indicator(self, key):
        def _show_key_indicator():
            try:
                root = tk.Tk()
                root.overrideredirect(True)
                root.attributes('-topmost', True)
                root.attributes('-alpha', 0.9)
                root.configure(bg='black')
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                width, height = 200, 100
                x = screen_width - width - 50
                y = 50
                root.geometry(f"{width}x{height}+{x}+{y}")
                if key in ['SPACE', 'ENTER', 'BACKSPACE']:
                    display_text = f"[{key}]"
                    font_size = 16
                else:
                    display_text = f"[{key}]"
                    font_size = 48
                label = tk.Label(
                    root,
                    text=display_text,
                    font=("Arial", font_size, "bold"),
                    fg="yellow",
                    bg="black",
                    justify="center"
                )
                label.pack(expand=True)
                instruction_label = tk.Label(
                    root,
                    text="Current Key",
                    font=("Arial", 12),
                    fg="white",
                    bg="black"
                )
                instruction_label.pack()
                root.after(3000, root.destroy)
                root.mainloop()
            except Exception as e:
                print(f"[KEY INDICATOR] Error: {e}")
        Thread(target=_show_key_indicator, daemon=True).start()

    def highlight_osk_key(self, key):
        def _highlight_key():
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                FindWindow = user32.FindWindowW
                GetWindowRect = user32.GetWindowRect
                PostMessage = user32.PostMessageW
                time.sleep(0.2)
                osk_hwnd = FindWindow("OSKMainClass", None)
                if not osk_hwnd:
                    print("⚠️ OSK window not found for highlighting")
                    return
                key_hwnd = self.find_osk_key_button(osk_hwnd, key)
                if key_hwnd:
                    WM_MOUSEMOVE = 0x0200
                    WM_MOUSEENTER = 0x02A2
                    WM_MOUSELEAVE = 0x02A3
                    rect = wintypes.RECT()
                    GetWindowRect(key_hwnd, ctypes.byref(rect))
                    center_x = (rect.left + rect.right) // 2
                    center_y = (rect.top + rect.bottom) // 2
                    local_x = (rect.right - rect.left) // 2
                    local_y = (rect.bottom - rect.top) // 2
                    lparam = (local_y << 16) | local_x
                    print(f"[OSK HIGHLIGHT] Highlighting key '{key}' at button handle {key_hwnd}")
                    PostMessage(key_hwnd, WM_MOUSEENTER, 0, 0)
                    PostMessage(key_hwnd, WM_MOUSEMOVE, 0, lparam)
                    time.sleep(2)
                    PostMessage(key_hwnd, WM_MOUSELEAVE, 0, 0)
                    print(f"[OSK HIGHLIGHT] ✅ Key '{key}' highlighted successfully")
                else:
                    print(f"⚠️ Could not find button for key '{key}' in OSK")
            except Exception as e:
                print(f"[OSK HIGHLIGHT] Error highlighting key: {e}")
        Thread(target=_highlight_key, daemon=True).start()

    def find_osk_key_button(self, osk_hwnd, target_key):
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            FindWindowEx = user32.FindWindowExW
            GetWindowText = user32.GetWindowTextW
            GetWindowTextLength = user32.GetWindowTextLengthW
            EnumChildWindows = user32.EnumChildWindows
            EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            found_button = [None]
            def enum_child_callback(hwnd, lParam):
                try:
                    length = GetWindowTextLength(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        GetWindowText(hwnd, buff, length + 1)
                        button_text = buff.value.strip()
                        if self.matches_key(button_text, target_key):
                            found_button[0] = hwnd
                            print(f"[OSK FIND] Found button for '{target_key}': text='{button_text}', hwnd={hwnd}")
                            return False
                except Exception as e:
                    pass
                return True
            EnumChildWindows(osk_hwnd, EnumChildProc(enum_child_callback), 0)
            return found_button[0]
        except Exception as e:
            print(f"[OSK FIND] Error finding key button: {e}")
            return None

    def matches_key(self, button_text, target_key):
        button_text = button_text.upper().strip()
        target_key = target_key.upper().strip()
        if button_text == target_key:
            return True
        special_mappings = {
            'SPACE': ['SPACE', 'SPACEBAR', ' '],
            'ENTER': ['ENTER', 'RETURN', 'RET'],
            'BACKSPACE': ['BACKSPACE', 'BACK', 'BKSP']
        }
        if target_key in special_mappings:
            return button_text in special_mappings[target_key]
        return False

    def show_system_wide_subtitle(self, text):
        def create_overlay():
            try:
                overlay_root = tk.Tk()
                overlay_root.title("Morse Subtitle")
                overlay_root.attributes('-topmost', True)
                overlay_root.attributes('-alpha', 0.9)
                overlay_root.overrideredirect(True)
                screen_width = overlay_root.winfo_screenwidth()
                screen_height = overlay_root.winfo_screenheight()
                overlay_width = min(800, len(text) * 15)
                overlay_height = 100
                x = (screen_width - overlay_width) // 2
                y = screen_height // 4
                overlay_root.geometry(f"{overlay_width}x{overlay_height}+{x}+{y}")
                overlay_root.configure(bg='black')
                label = tk.Label(overlay_root,
                               text=text,
                               font=('Arial', 18, 'bold'),
                               fg='lime',
                               bg='black',
                               wraplength=overlay_width-20)
                label.pack(expand=True)
                overlay_root.after(3000, overlay_root.destroy)
                overlay_root.mainloop()
            except Exception as e:
                print(f"Error creating overlay: {e}")
        Thread(target=create_overlay, daemon=True).start()

    def show_highlighted_key(self, key):
        def create_highlight():
            try:
                highlight_root = tk.Tk()
                highlight_root.title("Selected Key")
                highlight_root.attributes('-topmost', True)
                highlight_root.attributes('-alpha', 0.9)
                highlight_root.overrideredirect(True)
                screen_width = highlight_root.winfo_screenwidth()
                screen_height = highlight_root.winfo_screenheight()
                width, height = 150, 80
                x = screen_width - width - 20
                y = 20
                highlight_root.geometry(f"{width}x{height}+{x}+{y}")
                highlight_root.configure(bg='darkgreen')
                if key in ['SPACE', 'ENTER', 'BACKSPACE']:
                    display_text = key
                    font_size = 12
                else:
                    display_text = key
                    font_size = 24
                label = tk.Label(
                    highlight_root,
                    text=display_text,
                    font=("Arial", font_size, "bold"),
                    fg="white",
                    bg="darkgreen",
                    justify="center"
                )
                label.pack(expand=True)
                highlight_root.after(2000, root.destroy)
                highlight_root.mainloop()
            except Exception as e:
                print(f"Error creating key highlight: {e}")
        Thread(target=create_highlight, daemon=True).start()

    def draw_interface(self, frame, eye_count, avg_eyes, face_detected, is_blinking, avg_face_area, tilt_angle):
        h, w = frame.shape[:2]
        current_time = time.time()
        if self.tab_mode:
            pattern_display = "TAB MODE: A=Next Element, B=Previous Element"
            pattern_color = (255, 0, 255)
        elif self.keyboard_mode:
            current_key = self.keyboard_layout[self.keyboard_row][self.keyboard_col]
            pattern_display = f"KEYBOARD MODE: {current_key} | I=Up, N=Down, L=Left, R=Right, S=Select, X=Exit"
            pattern_color = (0, 255, 255)
        else:
            pattern_display = self.pattern if self.pattern else "Waiting for blinks..."
            pattern_color = (255, 255, 255)
        cv2.putText(frame, f"Pattern: {pattern_display}", (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, pattern_color, 2)
        cv2.putText(frame, "Morse Code Detector", (10, 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, f"EAR: {avg_eyes:.3f}", (10, 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        if is_blinking and self.blink_start_time:
            blink_duration = current_time - self.blink_start_time
            if blink_duration < self.dot_threshold:
                prediction = "DOT" if blink_duration > 0.01 else "BLINKING"
                prediction_color = (0, 255, 255)
            elif blink_duration >= self.dash_threshold:
                prediction = "DASH"
                prediction_color = (255, 165, 0)
            else:
                prediction = "BETWEEN"
                prediction_color = (255, 255, 0)
            cv2.putText(frame, f"🔴 {prediction} ({blink_duration:.2f}s)", (10, 95),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, prediction_color, 2)
            bar_width = int(min(blink_duration / 2.0, 1.0) * 200)
            cv2.rectangle(frame, (220, 85), (220 + bar_width, 100), prediction_color, -1)
            cv2.rectangle(frame, (220, 85), (420, 100), (100, 100, 100), 1)
            dot_threshold_x = int(220 + (self.dot_threshold / 2.0) * 200)
            dash_threshold_x = int(220 + (self.dash_threshold / 2.0) * 200)
            cv2.line(frame, (dot_threshold_x, 80), (dot_threshold_x, 105), (0, 255, 255), 2)
            cv2.line(frame, (dash_threshold_x, 80), (dash_threshold_x, 105), (255, 165, 0), 2)
        else:
            cv2.putText(frame, "👁️ Eyes Open", (10, 95),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if len(self.pattern) > 0:
            time_since_last = current_time - self.last_pattern_time
            time_left = self.letter_timeout - time_since_last
            if time_left > 0:
                bar_progress = (self.letter_timeout - time_left) / self.letter_timeout
                bar_width = int(bar_progress * 300)
                cv2.rectangle(frame, (10, 120), (10 + bar_width, 130), (255, 255, 0), -1)
                cv2.rectangle(frame, (10, 120), (310, 130), (100, 100, 100), 1)
                cv2.putText(frame, f"⏱️ Letter completes in: {time_left:.1f}s", (320, 128),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        if self.keyboard_mode:
            cv2.putText(frame, "⌨️ KEYBOARD MODE - I/N/L/R:Navigate | S:Select | X:Exit", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(frame, "A:Brave B:Notepad C:WhatsApp D:Keyboard | U:Undo Q:Close",
                   (10, h-60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(frame, "Keep face STRAIGHT | Press 'q' to quit",
                   (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    def draw_countdown_on_camera(self, frame):
        current_time = time.time()
        elapsed_time = current_time - self.startup_time
        remaining_time = self.startup_countdown_duration - elapsed_time
        if remaining_time > 0:
            self.system_active = False
            h, w = frame.shape[:2]
            countdown_text = f"System activating in: {int(remaining_time) + 1}"
            status_text = "MORSE DETECTION DISABLED"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.5
            thickness = 3
            padding = 20
            (text_width, text_height), baseline = cv2.getTextSize(countdown_text, font, font_scale, thickness)
            (status_width, status_height), _ = cv2.getTextSize(status_text, font, 0.8, 2)
            countdown_x = (w - text_width) // 2
            countdown_y = (h // 2) - 30
            status_x = (w - status_width) // 2
            status_y = countdown_y + 60
            cv2.rectangle(frame,
                         (countdown_x - padding, countdown_y - text_height - padding),
                         (countdown_x + text_width + padding, countdown_y + baseline + padding),
                         (0, 0, 0), -1)
            cv2.rectangle(frame,
                         (status_x - padding, status_y - status_height - padding),
                         (status_x + status_width + padding, status_y + baseline + padding),
                         (0, 0, 100), -1)
            cv2.putText(frame, countdown_text, (countdown_x, countdown_y),
                       font, font_scale, (0, 255, 255), thickness, cv2.LINE_AA)
            cv2.putText(frame, status_text, (status_x, status_y),
                       font, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
            progress_width = 400
            progress_height = 20
            progress_x = (w - progress_width) // 2
            progress_y = status_y + 50
            cv2.rectangle(frame, (progress_x, progress_y),
                         (progress_x + progress_width, progress_y + progress_height),
                         (50, 50, 50), -1)
            progress_fill = int((elapsed_time / self.startup_countdown_duration) * progress_width)
            if progress_fill > 0:
                cv2.rectangle(frame, (progress_x, progress_y),
                             (progress_x + progress_fill, progress_y + progress_height),
                             (0, 255, 0), -1)
        else:
            if not self.system_active:
                self.system_active = True
                self.subtitle = "🚀 Morse System ACTIVATED!"
                self.subtitle_time = time.time()
                print("🚀 Countdown finished - Morse detection system is now ACTIVE!")

    def check_system_active(self):
        current_time = time.time()
        elapsed_time = current_time - self.startup_time
        return elapsed_time >= self.startup_countdown_duration

    def process_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        results = self.face_mesh.process(frame_rgb)
        ear = None
        face_detected = False
        if results.multi_face_landmarks:
            face_detected = True
            lm = results.multi_face_landmarks[0].landmark
            left_ear = eye_aspect_ratio(lm, LEFT_EYE, w, h)
            right_ear = eye_aspect_ratio(lm, RIGHT_EYE, w, h)
            ear = (left_ear + right_ear) / 2.0
            self.ear_history.append(ear)
            for idx in LEFT_EYE + RIGHT_EYE:
                lm_xy = lm[idx]
                x, y = int(lm_xy.x*w), int(lm_xy.y*h)
                cv2.circle(frame, (x,y), 1, (0,255,0), -1)
        else:
            self.ear_history.append(1.0)
        smoothed_ear = float(np.mean(self.ear_history)) if len(self.ear_history) > 0 else 1.0
        is_closed = smoothed_ear < self.ear_threshold
        eye_count = 2 if not is_closed else 0
        avg_eyes = smoothed_ear
        current_time = time.time()
        if self.system_active:
            if is_closed and not self.currently_blinking:
                self.currently_blinking = True
                self.blink_start_time = current_time
                print("👁️ Blink started...")
            elif not is_closed and self.currently_blinking:
                self.currently_blinking = False
                if self.blink_start_time:
                    duration = current_time - self.blink_start_time
                    self.last_blink_duration = duration
                    self.total_blinks += 1
                    print(f"👁️ BLINK ENDED - Duration: {duration:.3f}s")
                    if duration < self.dot_threshold:
                        blink_type = "DOT (.)"
                        self.last_blink_type = blink_type
                        self.pattern += "."
                        print("🔵" + "="*40)
                        print(f"🔵 RESULT: {blink_type}")
                        print(f"🔵 MORSE CODE: .")
                        print(f"🔵 Duration: {duration:.3f}s")
                        print("🔵" + "="*40)
                        print(f"• Pattern now: '{self.pattern}'")
                        self.show_pattern_subtitle()
                        self.show_pattern_overlay(self.pattern)
                        self.last_pattern_time = time.time()
                    elif duration >= self.dash_threshold:
                        blink_type = "DASH (-)"
                        self.last_blink_type = blink_type
                        self.pattern += "-"
                        print("🔴" + "="*40)
                        print(f"🔴 RESULT: {blink_type}")
                        print(f"🔴 MORSE CODE: -")
                        print(f"🔴 Duration: {duration:.3f}s")
                        print("🔴" + "="*40)
                        print(f"— Pattern now: '{self.pattern}'")
                        self.show_pattern_subtitle()
                        self.show_pattern_overlay(self.pattern)
                        self.last_pattern_time = time.time()
                    else:
                        blink_type = "IGNORED"
                        self.last_blink_type = f"IGNORED ({duration:.3f}s)"
                        print("⚪" + "="*40)
                        print(f"⚪ RESULT: {blink_type}")
                        print(f"⚪ MORSE CODE: (none - between thresholds)")
                        print(f"⚪ Duration: {duration:.3f}s")
                        print(f"⚪ Need: <{self.dot_threshold}s for DOT or >={self.dash_threshold}s for DASH")
                        print("⚪" + "="*40)
                    self.blink_start_time = None
        self.check_complete_letter()
        self.draw_countdown_on_camera(frame)
        self.draw_immediate_subtitle(frame)
        self.draw_interface(frame, eye_count, avg_eyes, face_detected, self.currently_blinking, 0, 0)
        return frame

    def close_osk(self):
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            FindWindow = user32.FindWindowW
            PostMessage = user32.PostMessageW
            osk_hwnd = FindWindow("OSKMainClass", None)
            if not osk_hwnd:
                print("[OSK] OSK window not found")
                return False
            WM_SYSCOMMAND = 0x0112
            SC_CLOSE = 0xF060
            result = PostMessage(osk_hwnd, WM_SYSCOMMAND, SC_CLOSE, 0)
            if result:
                print("[OSK] ✅ Closed using WM_SYSCOMMAND SC_CLOSE")
                return True
            else:
                print("[OSK] ❌ WM_SYSCOMMAND failed, trying fallback methods")
            if pyautogui:
                try:
                    GetWindowRect = user32.GetWindowRect
                    rect = wintypes.RECT()
                    GetWindowRect(osk_hwnd, ctypes.byref(rect))
                    close_x = rect.right - 23
                    close_y = rect.top + 14
                    pyautogui.click(close_x, close_y)
                    print(f"[OSK] ✅ Clicked close button at ({close_x}, {close_y})")
                    return True
                except Exception as e:
                    print(f"[OSK] ❌ Mouse click method failed: {e}")
            if pyautogui:
                try:
                    SetForegroundWindow = user32.SetForegroundWindow
                    SetForegroundWindow(osk_hwnd)
                    time.sleep(0.1)
                    pyautogui.hotkey('alt', 'f4')
                    print("[OSK] ✅ Used Alt+F4 fallback method")
                    return True
                except Exception as e:
                    print(f"[OSK] ❌ Alt+F4 method failed: {e}")
            return False
        except Exception as e:
            print(f"[OSK] ❌ Error in close_osk: {e}")
            return False

    def resolve_context_letter(self, pattern):
        if self.keyboard_mode:
            context_map = {
                '.-': 'S',
                '-.': 'N',
                '..': 'I',
            }
            if pattern in context_map:
                return context_map[pattern]
        else:
            context_map = {
                '.-': 'A',
                '-.': 'B',
                '..': 'C',
            }
            if pattern in context_map:
                return context_map[pattern]
        return self.morse_dict.get(pattern)

    def get_visible_windows(self):
        """Return a list of visible window handles"""
        if not win32gui:
            return []
        windows = []
        def enum_windows_callback(hwnd, windows_list):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                windows_list.append(hwnd)
            return True
        win32gui.EnumWindows(enum_windows_callback, windows)
        return windows

    def show_letter_popup(self, letter):
        def create_popup():
            try:
                root = tk.Tk()
                root.overrideredirect(True)
                root.attributes('-topmost', True)
                root.attributes('-alpha', 0.9)
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                width, height = 300, 100
                x = (screen_width - width) // 2
                y = (screen_height - height) // 4
                root.geometry(f"{width}x{height}+{x}+{y}")
                root.configure(bg='black')
                label = tk.Label(root,
                               text=f"Letter: {letter}",
                               font=('Arial', 24, 'bold'),
                               fg='lime',
                               bg='black')
                label.pack(expand=True)
                root.after(2000, root.destroy)
                root.mainloop()
            except Exception as e:
                print(f"Error creating popup: {e}")
        Thread(target=create_popup, daemon=True).start()
        if self.keyboard_mode and letter in ['I', 'N', 'L', 'R', 'S', 'X']:
            if letter == 'I':
                self.keyboard_row = max(0, self.keyboard_row - 1)
                self.show_current_key()
                print("[KEYBOARD NAV] Moved UP")
            elif letter == 'N':
                self.keyboard_row = min(len(self.keyboard_layout) - 1, self.keyboard_row + 1)
                self.show_current_key()
                print("[KEYBOARD NAV] Moved DOWN")
            elif letter == 'L':
                self.keyboard_col = max(0, self.keyboard_col - 1)
                self.show_current_key()
                print("[KEYBOARD NAV] Moved LEFT")
            elif letter == 'R':
                max_col = len(self.keyboard_layout[self.keyboard_row]) - 1
                self.keyboard_col = min(max_col, self.keyboard_col + 1)
                self.show_current_key()
                print("[KEYBOARD NAV] Moved RIGHT")
            elif letter == 'S':
                current_key = self.keyboard_layout[self.keyboard_row][self.keyboard_col]
                if pyautogui:
                    if current_key == 'SPACE':
                        pyautogui.press('space')
                    elif current_key == 'ENTER':
                        pyautogui.press('enter')
                    elif current_key == 'BACKSPACE':
                        pyautogui.press('backspace')
                    else:
                        pyautogui.press(current_key.lower())
                self.show_highlighted_key(current_key)
                print(f"[KEYBOARD NAV] Selected key: {current_key}")
            elif letter == 'X':
                self.keyboard_mode = False
                if self.close_osk():
                    self.show_system_wide_subtitle("⌨️ Keyboard Mode Exited")
                    print("[KEYBOARD NAV] Exited keyboard mode and closed OSK")
                else:
                    self.show_system_wide_subtitle("❌ Failed to close OSK")
                    print("[KEYBOARD NAV] Failed to close OSK")
        elif letter == 'Y':
            self.tab_mode = not self.tab_mode
            mode_text = "ON" if self.tab_mode else "OFF"
            self.show_system_wide_subtitle(f"🗂️ Tab Mode {mode_text}")
            print(f"[MODE] Tab mode toggled to {mode_text}")
        elif letter == 'U':
            if self.app_stack:
                app = self.app_stack.pop()
                if pyautogui:
                    try:
                        pyautogui.hotkey('alt', 'f4')
                        self.show_system_wide_subtitle(f"🔙 Closed {app}")
                        print(f"[ACTION] Closed last app: {app}")
                    except Exception as e:
                        self.show_system_wide_subtitle(f"❌ Failed to close {app}")
                        print(f"[ACTION] Error closing last app: {e}")
            else:
                self.show_system_wide_subtitle("🔙 No apps to close")
                print("[ACTION] No apps in stack to close")
        elif letter == 'V':
            if pyautogui:
                try:
                    pyautogui.press('enter')
                    self.show_system_wide_subtitle("⏎ Enter Key Pressed")
                    print("[ACTION] Enter key pressed")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to press Enter")
                    print(f"[ACTION] Error pressing Enter: {e}")
        elif letter == 'M':
            if pyautogui and win32gui:
                try:
                    windows = self.get_visible_windows()
                    if len(windows) > 1:  # Need at least 2 windows to switch
                        self.window_switch_count += 1
                        pyautogui.keyDown('ctrl')
                        pyautogui.keyDown('alt')
                        time.sleep(0.2)
                        for _ in range(self.window_switch_count % len(windows) or 1):
                            pyautogui.press('tab')
                            time.sleep(0.2)
                        pyautogui.keyUp('alt')
                        pyautogui.keyUp('ctrl')
                        self.show_system_wide_subtitle(f"🔄 Switched to App {self.window_switch_count}")
                        print(f"[ACTION] Switched to app {self.window_switch_count} ({len(windows)} windows)")
                    else:
                        self.show_system_wide_subtitle("❌ Too few windows to switch")
                        print("[ACTION] Not enough visible windows to switch")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to switch app")
                    print(f"[ACTION] Error switching app: {e}")
            elif pyautogui:
                try:
                    pyautogui.hotkey('alt', 'tab')
                    self.window_switch_count += 1
                    self.show_system_wide_subtitle(f"🔄 Switched to App {self.window_switch_count} (fallback)")
                    print(f"[ACTION] Switched to app {self.window_switch_count} (fallback)")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to switch app")
                    print(f"[ACTION] Error switching app (fallback): {e}")
            else:
                self.show_system_wide_subtitle("❌ App switching unavailable")
                print("[ACTION] pyautogui not installed, cannot switch apps")
        elif letter == 'E':
            if pyautogui:
                try:
                    pyautogui.click()
                    self.show_system_wide_subtitle("🖱️ Left Click")
                    print("[ACTION] Left click executed")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to left click")
                    print(f"[ACTION] Error left clicking: {e}")
        elif letter == 'Z':
            if pyautogui:
                try:
                    pyautogui.rightClick()
                    self.show_system_wide_subtitle("🖱️ Right Click")
                    print("[ACTION] Right click executed")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to right click")
                    print(f"[ACTION] Error right clicking: {e}")
        elif letter == 'W':
            if pyautogui and win32gui:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd and win32gui.IsWindowVisible(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                        self.show_system_wide_subtitle("🔽 Window Minimized")
                        print("[WINDOW] Minimized current window via win32gui")
                    else:
                        pyautogui.hotkey('win', 'down')
                        self.show_system_wide_subtitle("🔽 Window Minimized (fallback)")
                        print("[WINDOW] Minimized current window via pyautogui")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to minimize window")
                    print(f"[WINDOW] Error minimizing window: {e}")
            elif pyautogui:
                try:
                    pyautogui.hotkey('win', 'down')
                    self.show_system_wide_subtitle("🔽 Window Minimized")
                    print("[WINDOW] Minimized current window via pyautogui")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to minimize window")
                    print(f"[WINDOW] Error minimizing window: {e}")
            else:
                self.show_system_wide_subtitle("❌ Minimize unavailable")
                print("[WINDOW] pyautogui not installed, cannot minimize")
        elif letter == 'Q':
            if pyautogui:
                try:
                    pyautogui.hotkey('alt', 'f4')
                    self.show_system_wide_subtitle("🗙 Window Closed (Alt+F4)")
                    print("[WINDOW] Closed current window")
                except Exception as e:
                    self.show_system_wide_subtitle("❌ Failed to close window")
                    print(f"[WINDOW] Error closing window: {e}")
        elif self.tab_mode and letter in ['A', 'B']:
            if letter == 'A':
                if pyautogui:
                    try:
                        pyautogui.press('tab')
                        self.subtitle = "⭢ Next Element"
                        self.subtitle_time = time.time()
                        print("[TAB MODE] Next element (Tab)")
                    except Exception as e:
                        self.subtitle = "❌ Failed to tab"
                        self.subtitle_time = time.time()
                        print(f"[TAB MODE] Error pressing Tab: {e}")
            elif letter == 'B':
                if pyautogui:
                    try:
                        pyautogui.hotkey('shift', 'tab')
                        self.subtitle = "⭠ Previous Element"
                        self.subtitle_time = time.time()
                        print("[TAB MODE] Previous element (Shift+Tab)")
                    except Exception as e:
                        self.subtitle = "❌ Failed to shift+tab"
                        self.subtitle_time = time.time()
                        print(f"[TAB MODE] Error pressing Shift+Tab: {e}")
        elif not self.tab_mode and not self.keyboard_mode and letter == 'A':
            print("🌐 Opening Brave browser...")
            try:
                subprocess.Popen(["start", "brave"], shell=True)
                self.app_stack.append("brave")
                self.show_system_wide_subtitle("🌐 Brave Browser Opened!")
                print("✅ Brave launched successfully!")
            except Exception as e:
                print(f"❌ Error launching Brave: {e}")
                self.show_system_wide_subtitle("❌ Error: Could not open Brave")
        elif not self.tab_mode and not self.keyboard_mode and letter == 'B':
            print("📝 Opening Notepad...")
            try:
                subprocess.Popen(["notepad"], shell=True)
                self.app_stack.append("notepad")
                self.show_system_wide_subtitle("📝 Notepad Editor Opened!")
                print("✅ Notepad launched successfully!")
            except Exception as e:
                print(f"❌ Error launching Notepad: {e}")
                self.show_system_wide_subtitle("❌ Error: Could not open Notepad")
        elif not self.tab_mode and not self.keyboard_mode and letter == 'C':
            print("💬 Opening WhatsApp...")
            try:
                whatsapp_launched = False
                # Try Windows Store command with alternative AppUserModelID
                try:
                    subprocess.Popen(["start", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"], shell=True)
                    whatsapp_launched = True
                    print("✅ WhatsApp launched via Windows Store command")
                except Exception as e:
                    print(f"[WHATSAPP] Windows Store command failed: {e}")
                # Try additional Windows Store ID (in case of version differences)
                if not whatsapp_launched:
                    try:
                        subprocess.Popen(["start", "shell:AppsFolder\\WhatsAppDesktopBeta_pz6e5knx4mh1m!App"], shell=True)
                        whatsapp_launched = True
                        print("✅ WhatsApp launched via alternative Windows Store command")
                    except Exception as e:
                        print(f"[WHATSAPP] Alternative Windows Store command failed: {e}")
                # Try common Desktop app paths
                if not whatsapp_launched:
                    whatsapp_paths = [
                        r"C:\Users\%USERNAME%\AppData\Local\WhatsApp\WhatsApp.exe",
                        r"C:\Program Files\WhatsApp\WhatsApp.exe",
                        r"C:\Program Files (x86)\WhatsApp\WhatsApp.exe"
                    ]
                    for path in whatsapp_paths:
                        expanded_path = os.path.expandvars(path)
                        if os.path.exists(expanded_path):
                            subprocess.Popen([expanded_path], shell=True)
                            whatsapp_launched = True
                            print(f"✅ WhatsApp launched from {expanded_path}")
                            break
                        else:
                            print(f"[WHATSAPP] Path not found: {expanded_path}")
                # Fallback to WhatsApp Web in Brave
                if not whatsapp_launched:
                    subprocess.Popen(["start", "brave", "https://web.whatsapp.com"], shell=True)
                    whatsapp_launched = True
                    print("✅ WhatsApp Web launched in Brave")
                if whatsapp_launched:
                    self.app_stack.append("whatsapp")
                    self.show_system_wide_subtitle("💬 WhatsApp Opened!")
                else:
                    raise Exception("All launch methods failed")
            except Exception as e:
                print(f"❌ Error launching WhatsApp: {e}")
                self.show_system_wide_subtitle("❌ Error: Could not open WhatsApp. Ensure it is installed.")
        elif not self.tab_mode and not self.keyboard_mode and letter == 'D':
            print("⌨️ Opening Virtual Keyboard with Navigation...")
            try:
                subprocess.Popen(["osk"], shell=True)
                self.app_stack.append("osk")
                self.keyboard_mode = True
                self.keyboard_row = 0
                self.keyboard_col = 0
                self.show_system_wide_subtitle("⌨️ Virtual Keyboard + Navigation Mode!")
                print("✅ Virtual Keyboard with navigation mode activated!")
                print("📍 Navigation: I=Up, N=Down, L=Left, R=Right, S=Select")
                self.show_current_key()
            except Exception as e:
                print(f"❌ Error launching Virtual Keyboard: {e}")
                self.show_system_wide_subtitle("❌ Error: Could not open Virtual Keyboard")
        else:
            print(f"❓ No application mapped to letter: {letter}")
            self.subtitle = f"❓ No app mapped to: {letter}"
            self.subtitle_time = time.time()

def main():
    detector = MorseDetector()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Error: Could not open video capture")
        return
    print("📷 Press 'q' to quit")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Error: Could not read frame from webcam")
            break
        frame = detector.process_frame(frame)
        cv2.imshow("Morse Code Detector", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
