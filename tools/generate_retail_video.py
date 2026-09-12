import os
import cv2
import numpy as np
from pathlib import Path
import math

def create_synthetic_retail_video(output_path="videos/store.mp4", duration_sec=24, fps=30):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    width, height = 1280, 720
    total_frames = duration_sec * fps
    
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    print(f"Generating realistic retail CCTV video with Staff vs Customer AI at {output_path} ({total_frames} frames)...")
    
    # Store Layout Static Background
    bg = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Floor - retail tile pattern
    for y in range(0, height, 40):
        for x in range(0, width, 40):
            tile_color = (238, 242, 246) if ((x // 40) + (y // 40)) % 2 == 0 else (228, 232, 238)
            cv2.rectangle(bg, (x, y), (x + 40, y + 40), tile_color, -1)
            cv2.rectangle(bg, (x, y), (x + 40, y + 40), (210, 215, 222), 1)

    for frame_idx in range(total_frames):
        frame = bg.copy()
        
        # 1. Draw Shelf Structures
        # --- Shelf 1 (Snacks & Biscuits) ---
        cv2.rectangle(frame, (40, 40), (520, 270), (70, 60, 50), -1)
        cv2.rectangle(frame, (45, 45), (515, 265), (95, 85, 75), -1)
        cv2.rectangle(frame, (45, 145), (515, 155), (55, 45, 35), -1)
        cv2.rectangle(frame, (45, 255), (515, 265), (55, 45, 35), -1)
        cv2.putText(frame, "SHELF A: SNACKS & CONFECTIONERY", (55, 35), cv2.FONT_HERSHEY_DUPLEX, 0.55, (40, 30, 20), 2)
        
        # --- Shelf 2 (Beverages & Juices) ---
        cv2.rectangle(frame, (40, 330), (520, 580), (50, 60, 70), -1)
        cv2.rectangle(frame, (45, 335), (515, 575), (75, 85, 95), -1)
        cv2.rectangle(frame, (45, 445), (515, 455), (40, 50, 60), -1)
        cv2.rectangle(frame, (45, 565), (515, 575), (40, 50, 60), -1)
        cv2.putText(frame, "SHELF B: BEVERAGES & COLD DRINKS", (55, 325), cv2.FONT_HERSHEY_DUPLEX, 0.55, (20, 30, 40), 2)

        # --- Shelf 3 (Dairy & Daily Essentials) ---
        cv2.rectangle(frame, (800, 40), (1240, 270), (60, 70, 60), -1)
        cv2.rectangle(frame, (805, 45), (1235, 265), (85, 95, 85), -1)
        cv2.rectangle(frame, (805, 145), (1235, 155), (45, 55, 45), -1)
        cv2.rectangle(frame, (805, 255), (1235, 265), (45, 55, 45), -1)
        cv2.putText(frame, "SHELF C: DAIRY & ESSENTIALS", (815, 35), cv2.FONT_HERSHEY_DUPLEX, 0.55, (30, 40, 30), 2)

        # --- Checkout Counter & Queue Area ---
        cv2.rectangle(frame, (830, 360), (1240, 680), (200, 210, 215), -1)
        cv2.rectangle(frame, (830, 360), (1240, 680), (140, 150, 160), 2)
        cv2.rectangle(frame, (1090, 420), (1220, 630), (100, 110, 120), -1)
        cv2.putText(frame, "BILLING COUNTER 1 (POS ACTIVE)", (850, 390), cv2.FONT_HERSHEY_DUPLEX, 0.55, (30, 40, 50), 2)
        cv2.putText(frame, "POS TERMINAL", (1105, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (240, 240, 240), 1)

        # 2. Draw Products on Shelves
        # Fanta Orange (4 bottles -> 1 -> 0 OOS)
        fanta_count = 4
        if frame_idx >= 380:
            fanta_count = 0
        elif frame_idx >= 180:
            fanta_count = 1
            
        for i in range(fanta_count):
            bx = 60 + i * 38
            by = 360
            cv2.rectangle(frame, (bx, by + 12), (bx + 30, by + 68), (0, 140, 255), -1)
            cv2.rectangle(frame, (bx + 8, by), (bx + 22, by + 12), (50, 200, 50), -1)
            cv2.putText(frame, "Fanta", (bx + 1, by + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        # Price tag under Fanta
        cv2.rectangle(frame, (60, 430), (140, 444), (245, 245, 245), -1)
        cv2.rectangle(frame, (60, 430), (140, 444), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 35", (75, 441), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        # Real Orange Juice
        juice_count = 3 if frame_idx < 350 else 1
        for i in range(juice_count):
            bx = 220 + i * 40
            by = 360
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 68), (20, 160, 240), -1)
            cv2.putText(frame, "Real", (bx + 2, by + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)

        # Tag under Real Juice
        cv2.rectangle(frame, (220, 430), (300, 444), (245, 245, 245), -1)
        cv2.rectangle(frame, (220, 430), (300, 444), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 40", (235, 441), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        # Coca Cola (Tag says Rs 99 -> Triggers EasyOCR price mismatch alert!)
        coke_count = 3
        for i in range(coke_count):
            bx = 370 + i * 40
            by = 360
            cv2.rectangle(frame, (bx, by + 12), (bx + 30, by + 68), (30, 30, 200), -1)
            cv2.rectangle(frame, (bx + 8, by), (bx + 22, by + 12), (240, 240, 240), -1)
            cv2.putText(frame, "Coke", (bx + 1, by + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        cv2.rectangle(frame, (370, 430), (450, 444), (245, 245, 245), -1)
        cv2.rectangle(frame, (370, 430), (450, 444), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 99", (385, 441), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 200), 1)

        # Shelf A (Snacks)
        pringles_count = 3 if frame_idx < 260 else 1
        for i in range(pringles_count):
            bx = 60 + i * 42
            by = 65
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 65), (40, 40, 220), -1)
            cv2.putText(frame, "Pring", (bx + 1, by + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        cv2.rectangle(frame, (60, 132), (140, 146), (245, 245, 245), -1)
        cv2.rectangle(frame, (60, 132), (140, 146), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 110", (70, 143), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 0, 0), 1)

        oreo_count = 3
        for i in range(oreo_count):
            bx = 200 + i * 40
            by = 65
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 65), (180, 60, 20), -1)
            cv2.putText(frame, "Oreo", (bx + 2, by + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        cv2.rectangle(frame, (200, 132), (280, 146), (245, 245, 245), -1)
        cv2.rectangle(frame, (200, 132), (280, 146), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 30", (215, 143), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        lays_count = 3
        for i in range(lays_count):
            bx = 340 + i * 40
            by = 65
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 65), (20, 200, 240), -1)
            cv2.putText(frame, "Lays", (bx + 2, by + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (20, 20, 20), 1)

        cv2.rectangle(frame, (340, 132), (420, 146), (245, 245, 245), -1)
        cv2.rectangle(frame, (340, 132), (420, 146), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 20", (355, 143), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        # Shelf C (Dairy & Essentials)
        milk_count = 4 if frame_idx < 260 else 0
        for i in range(milk_count):
            bx = 820 + i * 40
            by = 65
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 65), (220, 220, 220), -1)
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 65), (180, 100, 50), 2)
            cv2.putText(frame, "Amul", (bx + 1, by + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (20, 20, 20), 1)

        cv2.rectangle(frame, (820, 132), (900, 146), (245, 245, 245), -1)
        cv2.rectangle(frame, (820, 132), (900, 146), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 30", (835, 143), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        dove_count = 3
        for i in range(dove_count):
            bx = 990 + i * 40
            by = 65
            cv2.rectangle(frame, (bx, by), (bx + 32, by + 60), (250, 250, 250), -1)
            cv2.putText(frame, "Dove", (bx + 1, by + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (100, 100, 100), 1)

        cv2.rectangle(frame, (990, 132), (1070, 146), (245, 245, 245), -1)
        cv2.rectangle(frame, (990, 132), (1070, 146), (50, 50, 50), 1)
        cv2.putText(frame, "Rs 40", (1005, 143), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

        # 3. DRAW STORE STAFF (Distinct Store Uniform / Apron in Cyan/Teal with Yellow Staff Badge)
        def draw_store_staff(img, cx, cy, staff_id, role_name):
            # Staff uniform: Bright Teal/Cyan Torso + Yellow ID Badge on chest
            cv2.circle(img, (int(cx), int(cy - 24)), 15, (220, 180, 140), -1) # Head
            # Cyan Uniform Apron
            cv2.rectangle(img, (int(cx - 16), int(cy - 8)), (int(cx + 16), int(cy + 36)), (212, 182, 6), -1) # Cyan BGR (6, 182, 212)
            # Yellow Staff ID Badge on chest
            cv2.rectangle(img, (int(cx - 6), int(cy)), (int(cx + 6), int(cy + 10)), (0, 215, 255), -1)
            cv2.circle(img, (int(cx), int(cy - 24)), 15, (30, 30, 30), 2)
            cv2.putText(img, f"Staff #{staff_id} ({role_name})", (int(cx - 65), int(cy - 34)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 2)
            cv2.putText(img, f"Staff #{staff_id} ({role_name})", (int(cx - 65), int(cy - 34)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)

        # Staff #201: Floor Associate (Monitors/replenishes Aisle B & A)
        staff_a_x = 440 + math.sin(frame_idx * 0.04) * 20
        staff_a_y = 480 + math.cos(frame_idx * 0.03) * 15
        draw_store_staff(frame, staff_a_x, staff_a_y, 201, "Floor Replenisher")

        # Staff #202: Cashier (Stationed at Checkout Counter 1)
        staff_b_x = 1140
        staff_b_y = 480
        draw_store_staff(frame, staff_b_x, staff_b_y, 202, "Cashier")

        # 4. DRAW CUSTOMERS / SHOPPERS (Civilian attire)
        def draw_customer(img, cx, cy, label_id, color=(200, 110, 40)):
            pw, ph = 48, 88
            px1, py1 = int(cx - pw // 2), int(cy - ph // 2)
            cv2.circle(img, (int(cx), int(cy - 24)), 15, color, -1)
            cv2.rectangle(img, (int(cx - 16), int(cy - 8)), (int(cx + 16), int(cy + 36)), color, -1)
            cv2.circle(img, (int(cx), int(cy - 24)), 15, (30, 30, 30), 2)
            cv2.putText(img, f"Shopper #{label_id}", (px1, max(15, py1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 2)
            cv2.putText(img, f"Shopper #{label_id}", (px1, max(15, py1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)

        # Shopper 101
        if 20 <= frame_idx:
            if frame_idx < 130:
                t = (frame_idx - 20) / 110
                cx, cy = 20 + t * 160, 450
            elif frame_idx < 220:
                cx, cy = 180, 460
            elif frame_idx < 320:
                t = (frame_idx - 220) / 100
                cx, cy = 180 + t * (870 - 180), 460 + t * (520 - 460)
            else:
                cx, cy = 870, 520
            draw_customer(frame, cx, cy, 101, (180, 120, 50))

        # Shopper 102
        if 60 <= frame_idx:
            if frame_idx < 160:
                t = (frame_idx - 60) / 100
                cx, cy = 20 + t * 240, 200 - t * 40
            elif frame_idx < 240:
                cx, cy = 260, 160
            elif frame_idx < 340:
                t = (frame_idx - 240) / 100
                cx, cy = 260 + t * (920 - 260), 160 + t * (520 - 160)
            else:
                cx, cy = 920, 520
            draw_customer(frame, cx, cy, 102, (60, 160, 100))

        # Shopper 103 (Suspect / Shoplifter in Demo Video)
        # Approaches Shelf C, takes Amul Milk, and exits through the corridor between Shelf C & Billing Counter without paying!
        if 120 <= frame_idx:
            if frame_idx < 200:
                t = (frame_idx - 120) / 80
                cx, cy = 20 + t * 860, 300 - t * 140 # Moves to Shelf C at (880, 160)
            elif frame_idx < 290:
                # Dwells at Shelf C (takes Amul Milk at frame 260)
                cx, cy = 880, 160
            elif frame_idx < 350:
                # Moves south into the corridor between Shelf C and Billing Counter (y=315)
                t = (frame_idx - 290) / 60
                cx = 880 + t * 40
                cy = 160 + t * 155 # y goes to 315 (inside exit corridor [760, 270, 1280, 359])
            elif frame_idx < 500:
                # Walks along the exit corridor towards the right exit, completely bypassing checkout
                t = (frame_idx - 350) / 150
                cx = 920 + t * 360 # x goes to 1280
                cy = 315 + math.sin(frame_idx * 0.1) * 3
            else:
                cx, cy = 1300, 315
            
            if frame_idx < 510:
                draw_customer(frame, cx, cy, 103, (80, 80, 200))

        # Shopper 104
        if 180 <= frame_idx:
            if frame_idx < 280:
                t = (frame_idx - 180) / 100
                cx, cy = 20 + t * 350, 500
            elif frame_idx < 360:
                t = (frame_idx - 280) / 80
                cx, cy = 370 + t * (1020 - 370), 500 + t * (520 - 500)
            else:
                cx, cy = 1020, 520
            draw_customer(frame, cx, cy, 104, (160, 80, 160))

        # Shopper 105
        if 240 <= frame_idx:
            if frame_idx < 360:
                t = (frame_idx - 240) / 120
                cx, cy = 20 + t * 1050, 600 - t * 80
            else:
                cx, cy = 1070, 520
            draw_customer(frame, cx, cy, 105, (40, 140, 220))

        # Shopper 106
        if 290 <= frame_idx:
            if frame_idx < 400:
                t = (frame_idx - 290) / 110
                cx, cy = 20 + t * 1100, 620 - t * 100
            else:
                cx, cy = 1120, 520
            draw_customer(frame, cx, cy, 106, (220, 80, 80))

        # Shopper 107
        if 80 <= frame_idx < 640:
            cx = 620 + math.sin(frame_idx * 0.05) * 40
            cy = 380 + math.cos(frame_idx * 0.03) * 60
            draw_customer(frame, cx, cy, 107, (120, 180, 60))

        # Shopper 108
        if 140 <= frame_idx < 680:
            cx = 720 + math.cos(frame_idx * 0.04) * 35
            cy = 220 + math.sin(frame_idx * 0.04) * 40
            draw_customer(frame, cx, cy, 108, (190, 60, 140))

        # Status Overlay Bar
        cv2.rectangle(frame, (0, 685), (width, height), (25, 25, 30), -1)
        cv2.putText(frame, f"CCTV CAM 01 | STAFF AI: 2 ON DUTY | LOSS PREVENTION: ACTIVE | OCR AUDIT: ON | TIME: {frame_idx/30:.1f}s", 
                    (20, 708), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 200), 1)

        writer.write(frame)
        
    writer.release()
    print(f"Realistic retail video with Staff vs Customer AI created: {output_path}")

if __name__ == "__main__":
    create_synthetic_retail_video()
