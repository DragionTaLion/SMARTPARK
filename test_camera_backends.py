import cv2

def test_backends():
    backends = [
        ("Default", cv2.CAP_ANY),
        ("DSHOW", cv2.CAP_DSHOW),
        ("MSMF", cv2.CAP_MSMF),
        ("V4L2", cv2.CAP_V4L2),
    ]
    
    for b_name, b_val in backends:
        print(f"Testing backend: {b_name}")
        for i in range(3):
            cap = cv2.VideoCapture(i, b_val)
            if cap.isOpened():
                print(f"  - Camera ID {i} is OPEN with {b_name}")
                cap.release()
            else:
                pass
    print("Done testing.")

if __name__ == "__main__":
    test_backends()
