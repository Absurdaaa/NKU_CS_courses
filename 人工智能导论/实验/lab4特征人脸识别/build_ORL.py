def process_face_image(image_path, output_path, target_size=(112, 92)):
    """处理人脸图像：检测、裁剪、调整大小和对齐"""
    # 读取图像
    img = cv2.imread(image_path)
    
    # 人脸检测（使用OpenCV的人脸检测器）
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    if len(faces) > 0:
        # 取第一个检测到的人脸
        (x, y, w, h) = faces[0]
        face_img = gray[y:y+h, x:x+w]
        
        # 检测眼睛
        eyes = eye_cascade.detectMultiScale(face_img)
        if len(eyes) >= 2:
            # 根据眼睛位置调整和对齐人脸
            # 这里简化处理，实际应用中可能需要更复杂的对齐算法
            pass
        
        # 调整大小
        face_resized = cv2.resize(face_img, target_size)
        
        # 保存处理后的图像
        cv2.imwrite(output_path, face_resized)
        return True
    
    return False
    
def create_face_dataset(input_dir, output_npz, target_size=(112, 92)):
    """将处理好的图像整合为NPZ格式"""
    all_faces = []
    all_labels = []
    person_id = 0
    
    # 遍历每个人的文件夹
    for person_folder in os.listdir(input_dir):
        person_path = os.path.join(input_dir, person_folder)
        if os.path.isdir(person_path):
            # 读取该人的所有人脸图像
            for img_name in os.listdir(person_path):
                if img_name.endswith(('.jpg', '.png', '.jpeg')):
                    img_path = os.path.join(person_path, img_name)
                    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    
                    # 确保尺寸一致
                    if img.shape != target_size:
                        img = cv2.resize(img, target_size)
                    
                    # 将图像flatten为向量
                    face_vector = img.flatten()
                    all_faces.append(face_vector)
                    all_labels.append(person_id)
            
            person_id += 1
    
    # 转换为NumPy数组
    data = np.array(all_faces)
    label = np.array(all_labels)
    
    # 保存为NPZ文件
    np.savez(output_npz, data=data, label=label)
    print(f"已创建数据集，包含{person_id}个人，共{len(all_faces)}张人脸图像")

# 使用示例
# create_face_dataset("./my_face_images", "./MyFaces.npz")


def merge_with_orl(orl_path, my_faces_path, output_path):
    """合并ORL数据集和自己的人脸数据集"""
    # 加载两个数据集
    orl = np.load(orl_path)
    my_faces = np.load(my_faces_path)
    
    # 合并数据和标签
    orl_data = orl['data']
    orl_label = orl['label']
    my_data = my_faces['data']
    my_label = my_faces['label']
    
    # 将自己数据集的标签值偏移（避免与ORL重复）
    max_orl_label = np.max(orl_label)
    my_label = my_label + max_orl_label + 1
    
    # 合并
    merged_data = np.vstack([orl_data, my_data])
    merged_label = np.concatenate([orl_label, my_label])
    
    # 保存
    np.savez(output_path, data=merged_data, label=merged_label)
    print(f"已合并数据集，共{len(merged_label)}张图像，{np.max(merged_label)+1}个人")