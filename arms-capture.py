import bpy
import math
import rospy
from hr_msgs.msg import pau
import dynamic_reconfigure.client


_joint_list = ['Shoulder_R:0','Shoulder_R:2','Arm_Twist_R:1','Elbow_R:0','Forearm_Twist_R:1','Wrist_R:2','Wrist_R:0','Index_Fing_Base_R:0','Mid_Base_R:0',
'Ring_Base_R:0','Pinky_Base_R:0','Thumb_Base_R:0','Thumb_Pivot_R:1','Thumb_Pivot_R:0','Shoulder_L:0','Shoulder_L:2','Arm_Twist_L:1','Elbow_L:0','Forearm_Twist_L:1',
'Wrist_L:2','Wrist_L:0','Index_Fing_Base_L:0','Mid_Base_L:0','Ring_Base_L:0','Pinky_Base_L:0','Thumb_Base_L:0','Thumb_Pivot_L:1','Thumb_Pivot_L:0', 'Body:0', 'Body:2']


class UIProperties(bpy.types.PropertyGroup):
    bpy.types.Scene.starting_pose = bpy.props.EnumProperty(
        name = "Starting Pose",
        default = 'none',
        items = [('stand', 'Stand', ''),
                 ('sit', 'Sit', ''),
                 ('none', 'None', '')]
    )
    bpy.types.Scene.recorded_arm = bpy.props.EnumProperty(
        name = "Choose Arm",
        default = 'both',
        items = [('right', 'Record Right Arm only', ''),
                 ('left', 'Record Left Arm Only', ''),
                 ('both', 'Record Both Arms', '')]
    )
    bpy.types.Scene.hz = bpy.props.IntProperty(
        name = "Recording Hz",
        default = 1,
        soft_min = 1,
        soft_max = 50
    )
    bpy.types.Scene.recording_speed = bpy.props.FloatProperty(
        name = "Recording Speed",
        default = 1,
        soft_min = 0.1,
        soft_max = 2,
        step = 10,
        precision = 2
    )
    bpy.types.Scene.torque = bpy.props.BoolProperty(
        name = "Torque",
        default = True
    )
    bpy.types.Scene.recording = bpy.props.BoolProperty(
        name = "Recording",
        default = False
    )
    bpy.types.Scene.globalTimerStarted = bpy.props.BoolProperty(
        name = "globalTimerStarted",
        default = False
    )
    bpy.types.Scene.liveUpdatePose = bpy.props.BoolProperty(
        name = "liveUpdatePose",
        default = False
    )


class StartNodeButtonOperator(bpy.types.Operator):
    bl_idname = "scene.start_node"
    bl_label = "Start Node"

    def execute(self, context):
        try:
            rospy.init_node("arms_capture")
            client = dynamic_reconfigure.client.Client('/hr/control/arms')
            if client.get_configuration()['arms_mode'] == 'torque_off':
                context.scene.torque = False
            rospy.Subscriber("/hr/actuators/current_state", pau, self.callback)
        except Exception as e:
            self.report({"WARNING"}, "Can\'t start the node with exception {}".format(e))

        return {'FINISHED'}

    def callback(self, msg):
        if RecordPoseButtonOperator.recording:
            if RecordPoseButtonOperator.counter == round(50/RecordPoseButtonOperator.hz):
                RecordPoseButtonOperator.msg_angles.append(msg.m_angles)
                RecordPoseButtonOperator.counter = 0
            RecordPoseButtonOperator.counter += 1
        RecordPoseButtonOperator.last_msg = msg


class RecordPoseButtonOperator(bpy.types.Operator):
    bl_idname = "scene.start_arm_record"
    bl_label = "Start Recording"

    hz = 0
    counter = 0
    msg_angles = []
    recording = False
    last_msg = None

    def execute(self, context):
        RecordPoseButtonOperator.hz = context.scene.hz
        RecordPoseButtonOperator.counter = 0
        RecordPoseButtonOperator.msg_angles = []
        context.scene.recording = True
        RecordPoseButtonOperator.recording = True

        return {'FINISHED'}
    

class StopRecordButtonOperator(bpy.types.Operator):
    bl_idname = "scene.stop_arm_record"
    bl_label = "Stop Recording"

    def execute(self, context):
        context.scene.recording = False
        RecordPoseButtonOperator.recording = False
        if context.scene.starting_pose == 'none':
            s1 = "ARM-MAIN_"
        elif context.scene.starting_pose == 'sit':
            s1 = "ARM-MAIN-SIT_"
        elif context.scene.starting_pose == 'stand':
            s1 = "ARM-MAIN-STAND_"
        if context.scene.recorded_arm == 'both':
            s2 = "1-B_"
        elif context.scene.recorded_arm == 'left':
            s2 = "1-L_"
        elif context.scene.recorded_arm == 'right':
            s2 = "1-R_"
        action = bpy.data.actions.new(s1 + s2 + "MyRecording")
        for i in range(len(RecordPoseButtonOperator.msg_angles)):
            if context.scene.starting_pose == 'none':
                frame = i * (48/context.scene.hz)/context.scene.recording_speed
            else:
                frame = i * (48/context.scene.hz)/context.scene.recording_speed + 96
            angles = RecordPoseButtonOperator.msg_angles[i]
            pose = dict(zip(_joint_list, angles))
            pose['Wrist_L:0'] = -pose['Wrist_L:0']
            del pose['Body:0']
            del pose['Body:2']
            if context.scene.recorded_arm == 'left':
                pose = {b:a for (b,a) in pose.items() if '_L' in b}
            elif context.scene.recorded_arm == 'right':
                pose = {b:a for (b,a) in pose.items() if '_R' in b}
            for b, a in pose.items():
                self.set_angle(action, frame, b, a)
        if context.scene.starting_pose != 'none':
            self.add_starting_pose(context, action)
        context.object.animation_data.action = action

        return {'FINISHED'}
    
    @staticmethod
    def set_angle(action, frame, bone, angle):
        (path,index) = bone.split(':')
        path = "pose.bones[\"%s\"].rotation_euler" %path
        index = int(index)
        angle = math.radians(angle)
        fc = action.fcurves.find(path, index)
        if not fc:
            fc = action.fcurves.new(path, index)
        fc.keyframe_points.insert(frame, angle)
    
    @staticmethod
    def add_starting_pose(context, action):
        if context.scene.starting_pose == 'stand':
            action_new = bpy.data.actions["ARM-MAIN-1"]
        elif context.scene.starting_pose == 'sit':
            action_new = bpy.data.actions["ARM-MAIN-2"]
        for fc in action.fcurves:
            if (fc.data_path == 'pose.bones["Wrist_R"].rotation_euler' and fc.array_index == 0):
                y = -0.03307855874300003
            elif (fc.data_path == 'pose.bones["Wrist_L"].rotation_euler' and fc.array_index == 0):
                y = -0.001886842423118651
            else:
                fc_new = action_new.fcurves.find(fc.data_path, fc.array_index)
                y = fc_new.keyframe_points[0].co.y
            fc.keyframe_points.insert(0, y)
            fc.keyframe_points.insert(fc.keyframe_points[0].co.x + 48, y)
            fc.keyframe_points.insert(fc.keyframe_points[-1].co.x + 48, y)
            fc.keyframe_points.insert(fc.keyframe_points[-1].co.x + 48, y)
            

class ToggleTorqueButtonOperator(bpy.types.Operator):
    bl_idname = "scene.change_torque"
    bl_label = "Change Torque"

    def execute(self, context):
        client = dynamic_reconfigure.client.Client('/hr/control/arms')
        if context.scene.torque:
            client.update_configuration({'arms_mode':'torque_off'})
            context.scene.torque = False
        else:
            client.update_configuration({'arms_mode':'animations'})
            context.scene.torque = True

        return{'FINISHED'}


class ToggleUpdateButtonOperator(bpy.types.Operator):
    bl_idname = "scene.toggle_update"
    bl_label = "Toggle Live Update"

    def execute(self, context):
        if not bpy.context.scene.liveUpdatePose:
            bpy.context.scene.globalTimerStarted = True
            bpy.context.scene.liveUpdatePose = True
            bpy.ops.wm.global_timer()
            bpy.ops.wm.live_update_pose()
        else:
            bpy.context.scene.globalTimerStarted = False
            bpy.context.scene.liveUpdatePose = False

        return {'FINISHED'}


class BLGlobalTimer(bpy.types.Operator):
    """Timer  Control"""
    bl_label = "Global Timer"
    bl_idname = 'wm.global_timer'

    _timer = None
    _maxFPS = 50

    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(1/self._maxFPS, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not context.scene.globalTimerStarted:
            return self.cancel(context)
        return {'PASS_THROUGH'}

    def cancel(self,context):
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
        return {'CANCELLED'}

    @classmethod
    def poll(cls, context):
        return True


class BLUpdatePose(bpy.types.Operator):
    """Playback Control"""
    bl_label = "Start Update"
    bl_idname = 'wm.live_update_pose'

    def modal(self, context, event):
        if not context.scene.liveUpdatePose:
            return self.cancel(context)
        if event.type == 'TIMER':
            if RecordPoseButtonOperator.last_msg is not None:
                pose = dict(zip(_joint_list, RecordPoseButtonOperator.last_msg.m_angles))
                pose['Wrist_L:0'] = -pose['Wrist_L:0']
                del pose['Body:0']
                del pose['Body:2']
                for i,a in pose.items():
                    self.set_angle(i, a)
        return {'PASS_THROUGH'}

    def set_angle(self, bone, angle):
        (b,a) = bone.split(':')
        angle = math.radians(angle)
        a = int(a)
        if a == 0:
            bpy.data.objects['AA'].pose.bones[b].rotation_euler.x = angle
        if a == 1:
            bpy.data.objects['AA'].pose.bones[b].rotation_euler.y = angle
        if a == 2:
            bpy.data.objects['AA'].pose.bones[b].rotation_euler.z = angle

    def execute(self, context):
        wm = context.window_manager
        wm.modal_handler_add(self)
        if not context.scene.globalTimerStarted:
            bpy.ops.wm.global_timer()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        return {'CANCELLED'}

    @classmethod
    def poll(cls, context):
        return True


class ArmCapturePanel(bpy.types.Panel):
    bl_label = "Record Arms"
    bl_idname = "scene.record_arms_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(self, context):    
        return True

    def draw(self, context):
        layout = self.layout
        layout.operator(StartNodeButtonOperator.bl_idname)
        if not context.scene.liveUpdatePose:
            self.layout.operator(ToggleUpdateButtonOperator.bl_idname, text = "Start Live Update")
        else:
            self.layout.operator(ToggleUpdateButtonOperator.bl_idname, text = "Stop Live Update")
        if context.scene.torque:
            layout.operator(ToggleTorqueButtonOperator.bl_idname, text = "Torque Off")
        else:
            layout.operator(ToggleTorqueButtonOperator.bl_idname, text = "Torque On")
        layout.prop(bpy.context.scene, "hz")
        layout.prop(bpy.context.scene, "recording_speed")
        layout.prop(bpy.context.scene, "starting_pose")
        layout.prop(bpy.context.scene, "recorded_arm")
        if context.scene.recording:
            layout.operator(StopRecordButtonOperator.bl_idname)
        else:
            layout.operator(RecordPoseButtonOperator.bl_idname)


bl_info = {"name": "Arm Capture", "category": "User"}

def register():
    bpy.utils.register_class(StartNodeButtonOperator)
    bpy.utils.register_class(RecordPoseButtonOperator)
    bpy.utils.register_class(StopRecordButtonOperator)
    bpy.utils.register_class(BLGlobalTimer)
    bpy.utils.register_class(BLUpdatePose)
    bpy.utils.register_class(ToggleTorqueButtonOperator)
    bpy.utils.register_class(ToggleUpdateButtonOperator)
    bpy.utils.register_class(ArmCapturePanel)
    bpy.utils.register_class(UIProperties)

def unregister():
    bpy.utils.unregister_class(StartNodeButtonOperator)
    bpy.utils.unregister_class(RecordPoseButtonOperator)
    bpy.utils.unregister_class(StopRecordButtonOperator)
    bpy.utils.unregister_class(BLGlobalTimer)
    bpy.utils.unregister_class(BLUpdatePose)
    bpy.utils.unregister_class(ToggleTorqueButtonOperator)
    bpy.utils.unregister_class(ToggleUpdateButtonOperator)
    bpy.utils.unregister_class(ArmCapturePanel)
    bpy.utils.unregister_class(UIProperties)

if __name__ == "__main__":
    register()
