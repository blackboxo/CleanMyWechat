from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from send2trash import send2trash

##################################################################
# 删除线程，支持多进程
##################################################################
qmut = QMutex()


class multiDeleteThread(QThread):
    delete_process_signal = pyqtSignal(int)  # 进度信号
    delete_complete_signal = pyqtSignal()  # 完成信号

    def __init__(self, fileList, dirList, share_thread_arr):
        super(multiDeleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.share_thread_arr = share_thread_arr

    def run(self):
        """执行删除操作"""
        try:
            # 处理文件删除
            for file_path in self.fileList:
                try:
                    send2trash(file_path)
                    qmut.lock()
                    self.share_thread_arr[0] += 1
                    self.delete_process_signal.emit(self.share_thread_arr[0])
                    qmut.unlock()
                except Exception as e:
                    print(f"删除文件失败: {file_path}, 错误: {str(e)}")
                    # 继续处理下一个文件，不中断整个线程

            # 处理目录删除
            for dir_path in self.dirList:
                try:
                    send2trash(dir_path)
                    qmut.lock()
                    self.share_thread_arr[0] += 1
                    self.delete_process_signal.emit(self.share_thread_arr[0])
                    qmut.unlock()
                except Exception as e:
                    print(f"删除目录失败: {dir_path}, 错误: {str(e)}")
                    # 继续处理下一个目录，不中断整个线程

            print('一个线程执行结束了')
        except Exception as e:
            print(f"线程执行异常: {str(e)}")
        finally:
            # 发出完成信号
            self.delete_complete_signal.emit()
