from roboflow import Roboflow
rf = Roboflow(api_key="z40LNNtoi7IWOu9vdAcp")
project = rf.workspace("vietnam-license-plate-sb0bc").project("vietnam-license-plate-h8t3n-lkodj")
version = project.version(1)
dataset = version.download("yolov8")
