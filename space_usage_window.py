# 用于显示空间占用结果的窗口类
class SpaceUsageWindow(Window):
    def __init__(self, usage_data):
        try:
            print("开始初始化SpaceUsageWindow")
            super().__init__()
            
            # 读取配置文件
            self.config_path = os.path.join(working_dir, "config.json")
            with open(self.config_path, encoding="utf-8") as fd:
                self.config = json.load(fd)
            print("配置文件读取完成")
        
            # 设置窗口属性
            self.setWindowTitle("微信空间占用")
            self.setGeometry(100, 100, 560, 400)  # 宽度从700缩小140，变为560
            self.setStyleSheet("* {font: 9pt '微软雅黑';}")
        
            # 创建主布局
            main_layout = QVBoxLayout()
            print("主布局创建完成")
        
            # 创建中央部件
            central_widget = QWidget()
            central_widget.setLayout(main_layout)
            self.setCentralWidget(central_widget)
            print("中央部件设置完成")
        
            # 创建表格，调整列数和列名
            # 移除微信ID列，添加是否清理和保留天数列
            self.table = QTableWidget(len(usage_data), 5, central_widget)
            self.table.setHorizontalHeaderLabels(["微信名称", "所在盘符", "占用空间", "是否清理", "保留天数"])
            print("表格创建完成")
        
            # 设置表格属性
            self.table.setColumnWidth(0, 100)  # 调整列宽以适应窗口
            self.table.setColumnWidth(1, 80)
            self.table.setColumnWidth(2, 120)
            self.table.setColumnWidth(3, 80)   # 调整列宽以适应窗口
            self.table.setColumnWidth(4, 80)   # 调整列宽以适应窗口
            self.table.horizontalHeader().setStretchLastSection(False)
        
            # 允许编辑
            self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        
            # 设置表格默认对齐方式为居中
            self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        
            # 设置表格样式，使复选框居中
            self.table.setStyleSheet("""
                QTableWidget::indicator {
                    subcontrol-origin: padding;
                    subcontrol-position: center;
                    margin: auto;
                }
                QTableWidget QAbstractItemView::item {
                    text-align: center;
                    vertical-align: middle;
                }
            """)
        
            # 填充数据
            print(f"开始填充表格数据，共有{len(usage_data)}行数据")
            for row, data in enumerate(usage_data):
                print(f"处理第{row+1}行数据：{data}")
                name_item = QTableWidgetItem(data["name"])
                drive_item = QTableWidgetItem(data["drive"])
                size_item = QTableWidgetItem(data["size"])
            
                # 设置单元格对齐方式
                name_item.setTextAlignment(Qt.AlignCenter)
                drive_item.setTextAlignment(Qt.AlignCenter)
                size_item.setTextAlignment(Qt.AlignCenter)
            
                # 设置只读列（微信名称、所在盘符、占用空间）
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                drive_item.setFlags(drive_item.flags() & ~Qt.ItemIsEditable)
                size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            
                # 添加到表格
                self.table.setItem(row, 0, name_item)
                self.table.setItem(row, 1, drive_item)
                self.table.setItem(row, 2, size_item)
                print(f"第{row+1}行基本数据填充完成")
            
                # 跳过总占用行，只处理用户行
                if data["id"] != "total":
                    # 更可靠的用户配置匹配：遍历所有data_dir路径，通过路径匹配用户
                    user_config = None
                    user_id = data["id"]
                
                    # 首先尝试直接匹配wechat_id
                    user_config = next((user for user in self.config["users"] if user["wechat_id"].lower() == user_id.lower()), None)
                
                    # 如果直接匹配失败，尝试通过路径匹配
                    if not user_config:
                        for i, user_dir in enumerate(self.config["data_dir"]):
                            dir_name = os.path.basename(user_dir)
                            if dir_name.lower() == user_id.lower() and i < len(self.config["users"]):
                                user_config = self.config["users"][i]
                                break
                
                    # 如果还是没有匹配到，创建默认配置
                    if not user_config:
                        # 查找是否有对应的用户配置
                        user_config = {
                            "wechat_id": user_id,
                            "clean_days": "365",
                            "is_clean": True,
                            "clean_pic_cache": True,
                            "clean_file": False,
                            "clean_pic": True,
                            "clean_video": True,
                            "is_timer": True,
                            "timer": "0h"
                        }
                
                    # 是否清理列（复选框+文字）
                    # 创建包含复选框和文字的自定义单元格
                    check_widget = QWidget()
                    check_layout = QHBoxLayout(check_widget)
                    check_layout.setContentsMargins(5, 2, 5, 2)
                    check_layout.setSpacing(5)
                
                    # 创建复选框
                    checkbox = QCheckBox()
                    checkbox.setChecked(user_config["is_clean"])
                    checkbox.setAlignment(Qt.AlignCenter)
                
                    # 创建文字标签
                    label = QLabel("清理")
                    label.setAlignment(Qt.AlignCenter)
                
                    # 将复选框和文字添加到布局
                    check_layout.addWidget(checkbox, 0, Qt.AlignRight)
                    check_layout.addWidget(label, 0, Qt.AlignLeft)
                    check_layout.addStretch()
                
                    # 存储行号和用户ID，以便信号处理
                    checkbox.setProperty("row", row)
                    checkbox.setProperty("user_id", user_id)
                    checkbox.stateChanged.connect(lambda state, c=checkbox: self.on_checkbox_changed(c))
                
                    # 设置单元格小部件
                    self.table.setCellWidget(row, 3, check_widget)
                
                    # 保留天数列（文本框）
                    clean_days = QTableWidgetItem()
                    clean_days.setText(str(user_config["clean_days"]))
                    clean_days.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, 4, clean_days)
                else:
                    # 总占用行的编辑列设置为不可编辑
                    for col in [3, 4]:
                        empty_item = QTableWidgetItem("")
                        empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(row, col, empty_item)
        
            # 连接单元格变化信号，实现实时保存
            self.table.itemChanged.connect(self.on_item_changed)
        
            # 添加表格到布局
            main_layout.addWidget(self.table)
        
            # 创建关闭按钮
            close_button = QPushButton("关闭")
            close_button.clicked.connect(self.close)
            close_button.setStyleSheet("""
                QPushButton {
                    background-color: #1890ff;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #40a9ff;
                }
            """)
        
            # 添加按钮到布局
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(close_button)
            button_layout.addStretch()
            main_layout.addLayout(button_layout)
            print("主布局设置完成")
        
            # 应用淡入动画
            self.doFadeIn()
            print("淡入动画应用完成")
        
            # 显示窗口
            self.show()
            print("窗口显示完成")
        except Exception as e:
            import traceback
            print(f"SpaceUsageWindow初始化失败：{str(e)}")
            print(f"错误堆栈：{traceback.format_exc()}")
    
    def on_checkbox_changed(self, checkbox):
        """处理复选框状态变化，实时保存配置"""
        # 获取复选框关联的用户ID
        user_id = checkbox.property("user_id")
        if not user_id:
            return
        
        # 查找该用户在配置中的索引
        user_index = -1
        for i, user in enumerate(self.config["users"]):
            if user["wechat_id"].lower() == user_id.lower():
                user_index = i
                break
        
        if user_index == -1:
            print(f"未找到用户 {user_id} 的配置")
            return
        
        # 更新是否清理配置
        self.config["users"][user_index]["is_clean"] = checkbox.isChecked()
        
        # 保存配置到文件
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"用户 {user_id} 的配置已保存")
        except Exception as e:
            print(f"保存配置失败：{str(e)}")
    
    def on_item_changed(self, item):
        """处理表格单元格变化，实时保存配置"""
        row = item.row()
        col = item.column()
        
        # 获取当前行的数据
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        
        user_id = name_item.text()
        
        # 跳过总占用行
        if user_id == "微信总占用":
            return
        
        # 查找该用户在配置中的索引，使用与初始化相同的匹配逻辑
        user_index = -1
        
        # 首先尝试直接匹配wechat_id
        for i, user in enumerate(self.config["users"]):
            if user["wechat_id"].lower() == user_id.lower():
                user_index = i
                break
        
        if user_index == -1:
            print(f"未找到用户 {user_id} 的配置")
            return
        
        # 根据列索引处理不同类型的变化
        if col == 4:  # 保留天数列
            # 更新保留天数配置
            try:
                days = int(item.text())
                if days < 0:
                    days = 0
                self.config["users"][user_index]["clean_days"] = str(days)
            except ValueError:
                # 如果输入不是数字，恢复原来的值
                item.setText(self.config["users"][user_index]["clean_days"])
                return
        
        # 保存配置到文件
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"用户 {user_id} 的配置已保存")
        except Exception as e:
            print(f"保存配置失败：{str(e)}")