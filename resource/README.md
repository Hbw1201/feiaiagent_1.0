# Resource 文件夹说明

## 📁 文件夹结构
```
resource/
├── images/           # 图片资源
│   ├── avatar.jpg    # 数字人头像（必需）
│   └── README.md     # 图片说明
└── README.md         # 本说明文件
```

## 🖼️ 图片要求

### 数字人头像 (avatar.jpg)
- **格式**: JPG、PNG 等常见格式
- **内容**: 单人正脸照片，无遮挡，清晰度高
- **尺寸**: 建议 512x512 到 1024x1024 像素
- **文件大小**: 建议 ≤ 5MB
- **质量**: 光线充足，表情自然，背景简洁

## ⚙️ 配置说明

### 1. 使用默认图片
将您的头像文件重命名为 `avatar.jpg` 并放在 `resource/images/` 文件夹中

### 2. 使用自定义路径
在环境变量中设置：
```bash
DIGITAL_HUMAN_IMAGE_PATH=/path/to/your/image.jpg
```

### 3. 环境变量优先级
1. 环境变量 `DIGITAL_HUMAN_IMAGE_PATH`（最高优先级）
2. 项目内默认图片 `resource/images/avatar.jpg`
3. 如果都不存在，系统会报错

## 🔧 注意事项

- 确保图片文件存在且可读
- 图片质量直接影响数字人生成效果
- 建议使用专业拍摄的照片
- 避免使用模糊、低分辨率或多人照片
