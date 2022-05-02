import time
import cv2
import mediapipe as mp
from numpy import newaxis
from pynput.mouse import Button, Controller
import win32api, win32con


class Hand:
    def __init__(self, drawLabels=False, moveThresh=0, suppressShake=True, frameSample=3):
        self.drawLabels = drawLabels  # boolean: draws connections of the hand landmarks
        self.moveThresh = moveThresh
        self.suppressShake = suppressShake


        self.display = (1920, 1080)  # (1920,1080) resolution
        self.boundStart = (40,40) #(320,40)
        self.boundBox = (560,400) #(280,400)
        
        self.tipIds = [4, 8, 12, 16, 20]
        self.fingersRaised = [0, 0, 0, 0, 0]
        self.pTime = 0

        self.frameRate = [0 for i in range(5)]
        self.prevInput = (0,0)
        self.acceleration = 1.5
        self.mouseCoords = (self.display[0]/2,self.display[1]/2)
        self.lastPos = [(0, 0) for i in range(frameSample)]

        self.mouse = Controller()
        self.clickThresh = 0.5
        self.lastClick = 0
        self.mouseRunning = True
        self.leftDown = False
        self.rightDown = False
        self.mouseAction = "None"

        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(False, 1, False, 0.5, 0.5) 
        self.mpDraw = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()

    def setAcc(self, acceleration):
        self.acceleration = acceleration

    def avg(self, lst):
        if len(lst) > 0:
            return sum(lst) / len(lst)
            
    def avgPos(self, lst):  # input of a matrix of x,y positions
        avgX = self.avg([x[0] for x in lst])
        avgY = self.avg([y[1] for y in lst])
        return [int(avgX), int(avgY)]

    def queue(self, lst, point):
        newQueue = lst[1:]
        newQueue.append(point)
        return newQueue
    
    def overThresh(self,startCoords, endCoords):
        if abs(startCoords[0] - endCoords[0]) > self.moveThresh or abs(startCoords[1] - endCoords[1]) > self.moveThresh:
            return True
        else:
            return False

    def mouseAcceleration(self, handLms, camSize, img):
        inputX = int(self.avg([handLms.landmark[item].x for item in [0, 9, 13]]) * camSize[0])
        inputY = int(self.avg([handLms.landmark[item].y for item in [0, 9, 13]]) * camSize[1])
        if (inputX > self.boundStart[0] and inputX < self.boundStart[0] + self.boundBox[0] 
        and inputY > self.boundStart[1] and inputY < self.boundStart[1] + self.boundBox[1]):
            self.inBounds = True
            moveX = (inputX - self.prevInput[0]) * 2
            moveY = (inputY - self.prevInput[1]) * 2
            
            if moveX < 0:
                moveX = -(abs(moveX) ** self.acceleration)
            else:
                moveX = moveX ** self.acceleration
            if moveY < 0:
                moveY = -(abs(moveY) ** self.acceleration)
            else:
                moveY = moveY ** self.acceleration
            
            mouseX = self.mouseCoords[0] + moveX
            mouseY = self.mouseCoords[1] + moveY
            if mouseX > self.display[0]:
                mouseX = self.display[0]
            if mouseX < 0:
                mouseX = 0
            if mouseY > self.display[1]:
                mouseY = self.display[1]
            if mouseY < 0:
                mouseY = 0
            self.mouseCoords = (mouseX, mouseY)
            self.lastPos = self.queue(self.lastPos, self.mouseCoords)
            avgPos = self.avgPos(self.lastPos)

            if self.overThresh(self.mouseCoords, avgPos):
                x =  int(self.mouseCoords[0] - avgPos[0])
                y =  int(self.mouseCoords[1] - avgPos[1])
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, x, y, 0, 0) #necessary for centered mouse programs
                #self.mouse.move(x, y)
                #self.mouse.position = avgPos
                
                self.prevInput = (inputX, inputY)
        else:
            self.inBounds = False
        
        cv2.circle(img, (inputX, inputY), 3, (255, 255, 0), -1)  # draws hand position

    def controlMouse(self):
        if self.fingersRaised[1:5] == [1,1,1,1]:# if 4 fingers, thumb not included, are raised
            if self.leftDown == False:
                self.mouse.press(Button.left)
                self.leftDown = True
                self.mouseAction = "Left"
        else:
            if self.leftDown == True:
                self.leftDown = False
                self.mouse.release(Button.left)
                self.mouseAction = "None"
        if self.fingersRaised[1:5] == [0,1,1,1]: # if 3 fingers, thumb not included and index not included, are raised
            if self.rightDown == False:
                self.mouse.press(Button.right)
                self.rightDown = True
                self.mouseAction = "Right"
        else:
            if self.rightDown == True:
                self.rightDown = False
                self.mouse.release(Button.right)
                self.mouseAction = "None"
            # index, middle and ring finger raised
            '''
            if self.fingersRaised[1:4] == [1, 1, 1]:
                if self.handY <= self.display[1] / 2:
                    scroll = int((self.display[1]/2 - self.handY)/100)
                else:
                    scroll = int(-(self.handY - self.display[1]/2)/100)
                self.mouse.scroll(0, scroll)
            '''
            # index and middle finger raised
        if self.leftDown == False and self.rightDown == False:
            if self.fingersRaised[1:3] == [1, 1]:
                if (time.time() - self.lastClick) > self.clickThresh:
                    self.mouse.click(Button.right, 1)
                    self.mouseAction = "Right Click"
                    self.lastClick = time.time()
            elif self.fingersRaised[1] == 1:  # index finger raised
                if (time.time() - self.lastClick) > self.clickThresh:
                    self.mouse.click(Button.left, 1)
                    self.mouseAction = "Left Click"
                    self.lastClick = time.time()


    def draw(self):
        success, img = self.cap.read()  # tuple of boolean success and image feed
        img = cv2.flip(img,1) #inverts camera feed
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(imgRGB)
        h, w, c = img.shape
        y_offset = 5  # vertical position offset for number label on finger landmarks
        if results.multi_hand_landmarks:
            for handLms in results.multi_hand_landmarks: #iterating through each hand
                #self.mpDraw.draw_landmarks(img, handLms, self.mpHands.HAND_CONNECTIONS)
                for id, lm in enumerate(handLms.landmark):
                    if self.drawLabels:
                        cv2.putText(img, str(id), (int(lm.x * w), int(lm.y * h - y_offset)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    if id % 4 == 0 and id > 4:
                        if lm.y < handLms.landmark[id - 2].y:
                            self.fingersRaised[id // 4 - 1] = 1
                        else:
                            self.fingersRaised[id // 4 - 1] = 0
                self.mouseAcceleration(handLms, (w, h), img)
            if self.mouseRunning and self.inBounds:
                self.controlMouse()

        cTime = time.time()
        curFps = round(1/(cTime - self.pTime))
        self.frameRate = self.queue(self.frameRate,curFps)
        avgFps = "FPS: " + str(round(self.avg(self.frameRate)))
        self.pTime = cTime

        cv2.putText(img, avgFps, (10, 20), cv2.FONT_HERSHEY_SIMPLEX,0.5, (0, 255, 0), 2)  # displays fps
        cv2.putText(img, self.mouseAction, (400, 20), cv2.FONT_HERSHEY_SIMPLEX,0.5, (0, 255, 0), 2)  # displays fps
        cv2.rectangle(img, self.boundStart,( self.boundStart[0] + self.boundBox[0] , self.boundStart[1] + self.boundBox[1]), (0, 0, 255), 2) #draws virtual mousepad area
        cv2.imshow('Camera1', img)  # shows camera feed
        cv2.waitKey(1)  # waits for 1ms
