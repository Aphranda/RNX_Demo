from .View import StatusPanelView
from .Model import StatusPanelModel
from .Controller import StatusPanelController

class StatusPanel(StatusPanelView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = StatusPanelModel()
        self.controller = StatusPanelController(self, self.model)
        
    def update_motion_status(self, axis: str, status: dict):
        self.controller.update_motion_status(axis, status)
    
    def update_src_status(self, status: dict):
        self.controller.update_src_status(status)
    
    @property
    def cal_file_loaded(self):
        return self.controller.cal_file_loaded
