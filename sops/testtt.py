import cv2
from ultralytics import YOLO

# Load model
model = YOLO("./dustbin_best.pt")
model.to("cuda")

# Load and resize image
image_data = cv2.imread('emptyTopViewImage.jpg')
image = cv2.resize(image_data, (640, 640))

# Run inference
results = model(image)[0]

# Create a copy to draw on
annotated_image = image.copy()

# Draw detections manually
for box in results.boxes:
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    cls_id = int(box.cls[0])
    conf = float(box.conf[0])
    label = f"{results.names[cls_id]} {conf:.2f}"

    # Draw box
    cv2.rectangle(annotated_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Draw label above box
    cv2.putText(annotated_image, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

# Show result
cv2.imshow("Detections", annotated_image)
cv2.waitKey(0)
cv2.destroyAllWindows()

# Optionally save
cv2.imwrite("output_with_custom_detections.jpg", annotated_image)
