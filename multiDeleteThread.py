from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from send2trash import send2trash

##################################################################
# 删除线程，支持多进程
##################################################################
qmut = QMutex()


class multiDeleteThread(QThread):
    delete_process_signal = pyqtSignal(int)  # 创建信号

    def __init__(self, fileList, dirList, share_thread_arr):
        super(multiDeleteThread, self).__init__()
        self.fileList = fileList
        self.dirList = dirList
        self.share_thread_arr = share_thread_arr


    def run(self):
        try:
            for file_path in self.fileList:
                send2trash(file_path)
                qmut.lock()
                self.share_thread_arr[0] += 1
                self.delete_process_signal.emit(self.share_thread_arr[0])
                qmut.unlock()

            for file_path in self.dirList:
                send2trash(file_path)
                qmut.lock()
                self.share_thread_arr[0] += 1
                self.delete_process_signal.emit(self.share_thread_arr[0])
                qmut.unlock()

            # self.exec_()  # 关闭线程
            print('一个线程执行结束了')
        except Exception as e:
            print(e)
