from tkinter import *
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk
import socket, threading,os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class ClienteGUI:
	
	# Initiation..
	def __init__(self, master, addr, port):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.addr = addr
		self.port = int(port)
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.openRtpPort()
		self.playMovie()
		self.frameNbr = 0
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create NextVideo button
		self.nextvideo = Button(self.master, width=20, padx=3, pady=3)
		self.nextvideo["text"] = "NextVideo"
		self.nextvideo["command"] = self.nextVideo
		self.nextvideo.grid(row=1, column=4, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 

	def setupMovie(self):
		"""Setup button handler."""
		if self.requestSent == -1:  # Verifica se a sessão ainda não foi iniciada
			self.rtspSeq += 1
			self.requestSent = 0  # Define o estado da solicitação como `SETUP`
			self.sendRtspRequest("SETUP")  # Envia a solicitação de `SETUP`
			print("Enviando solicitação SETUP ao servidor.")

	def pauseMovie(self):
		"""Pause button handler."""
		if self.requestSent == 1:  # Verifica se o vídeo está atualmente em `PLAY`
			self.rtspSeq += 1
			self.requestSent = 2  # Define o estado da solicitação como `PAUSE`
			self.sendRtspRequest("PAUSE")  # Envia a solicitação de `PAUSE`
			print("Enviando solicitação PAUSE ao servidor.")
			self.playEvent.set()  # Sinaliza para interromper a recepção de pacotes RTP

	def nextVideo(self):
		"""NextVideo button handler."""
		self.pauseMovie()  # Pausa o vídeo atual antes de trocar
		self.frameNbr = 0  # Reinicia o número do quadro
		self.rtspSeq += 1
		self.requestSent = -1  # Reinicia o estado para preparar uma nova sessão
		self.sendRtspRequest("NEXT")  # Envia uma solicitação para o próximo vídeo
		print("Solicitando o próximo vídeo.")

	def exitClient(self):
		"""Teardown button handler."""
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video
	
	def playMovie(self):
		"""Play button handler."""
		# Create a new thread to listen for RTP packets
		threading.Thread(target=self.listenRtp).start()
		self.playEvent = threading.Event()
		self.playEvent.clear()
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					print("Current Seq Num: " + str(currFrameNbr))
										
					if currFrameNbr > self.frameNbr: # Discard the late packet
						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				self.rtpSocket.shutdown(socket.SHUT_RDWR)
				self.rtpSocket.close()
				break
				
	
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port
			self.rtpSocket.bind((self.addr, self.port))
			print('\nBind \n')
		except:
			messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def sendRtspRequest(self, requestType):
		"""Send RTSP request to the server."""
		request = f"{requestType} {self.addr}:{self.port} RTSP/1.0\n"
		request += f"CSeq: {self.rtspSeq}\n"
		if requestType == "SETUP":
			request += f"Transport: RTP/UDP; client_port= {self.port}\n"
		elif requestType == "PAUSE" or requestType == "NEXT":
			request += f"Session: {self.sessionId}\n"
		
		self.rtspSocket.send(request.encode())
		print(f"RTSP request sent:\n{request}")


	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
