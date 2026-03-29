import cv2

def check_cameras(max_to_test=5):
    available_cameras = []
    for i in range(max_to_test):
        try:
            # Try with DSHOW for Windows first
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
            else:
                # Fallback to default backend
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available_cameras.append(i)
                    cap.release()
        except:
            pass
    return available_cameras

if __name__ == "__main__":
    cameras = check_cameras()
    if not cameras:
        print("No cameras found!")
    else:
        print(f"Available camera IDs: {cameras}")
