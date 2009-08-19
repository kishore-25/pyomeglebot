#!/usr/bin/env python
# Written by Jason Brandt, 2009
# A small amount of code was lifted from tizenkotoko's script, found here: http://code.google.com/p/pyomeglealicebot/
# Do whatever you'd like with this script; if you post it somewhere else, some credit would be nice :)
#
# Usage: ./omegle.py [logfile]
# If no logfile is supplied, a logfile will be created in the "logs" folder, named after the current timestamp

import aiml, json, os, cPickle, random, re, sys, threading, time, urllib, urllib2


START_URL = 'http://omegle.com/start'
STOP_URL = 'http://omegle.com/disconnect'
EVENTS_URL = 'http://omegle.com/events'
TYPING_URL = 'http://omegle.com/typing'
STYPING_URL = 'http://omegle.com/stoppedtyping'
SEND_URL = 'http://omegle.com/send'

LEARNFILE = 'aiml/pyOmegleALICE.xml'
BRAINFILE = 'brn.brn'
USR_SETTINGS = 'settings.p'
DEF_SETTINGS = 'settings.p.default'

DEBUG = True

def debug(message):
    if DEBUG == True:
        print('<DEBUG `%s`>' % message)

class OmegleError(Exception):
    def __init__(self, message=''):
        self.__message = message
        
    def __str__(self):
        return self.__message

class Bot(object):
    ''' A basic interface to the Omegle chat app '''
    
    def __init__(self, printLog=False, writeLog=None, storeLog=False, doRestart=False):
        # Whether or not to print the conversation log to stdout
        self.printLog = printLog
        # Whether or not to store the conversation log to self.log
        self.storeLog = storeLog
        # Write conversation log to the given string, or do nothing if it's set to None
        self.writeLog = writeLog
        # Whether or not to restart the conversation after it is finished
        self.doRestart = doRestart
        # Set other variables here:
        self.__setVars()
    
    def event_Message(self, message):
        ''' What to do when the bot receives a new message '''
        pass
        
    def event_Typing(self):
        ''' What to do when the stranger is typing '''
        pass
        
    def start(self):
        ''' Start a conversation '''
        class eventThread(threading.Thread):
            ''' Thread will start a getEvents() loop '''
            def __init__(self, parent):
                threading.Thread.__init__(self)
                self.parent = parent
                
            def run(self):
                while self.parent.connected == True:
                    try:
                        debug('Getting events')
                        self.parent.getEvents()
                    except KeyboardInterrupt:
                         self.parent.stop()
        
        # Get our conversation ID from the server     
        self.id = urllib2.urlopen(START_URL, urllib.urlencode({})).read()
        self.id = re.sub('"', '', self.id)
        
        postData = urllib.urlencode({'id': self.id})
        
        self.connected = True
        eThread = eventThread(self)
        eThread.start()
         
    def stop(self):
        ''' Disconnect from the conversation '''
        urllib2.urlopen(STOP_URL, self.__encId())
        self.logMessage('[Bot disconnected]')
        self.connected = False
        
    def restart(self):
        ''' Disconnect from the conversation and start a new one '''
        self.stop()
        self.__setVars()
        self.start()
        
    def __setVars(self):
        ''' Set all conversation variables to their default values '''
        # self.messages:
        # [0] -> Bot's messages
        # [1] -> Stranger's messages
        self.messages = [[], []]
        # self.__typing is used internally for the self.typing magic variable
        self.__typing = False
        # Whether the bot is connected to a conversation
        self.connected = False
        # Our conversation logs
        self.log = []
        # Our conversation ID (will be fetched from the server later)
        self.id = None     
        
    def logMessage(self, message):
        ''' Print conversations messages to a file and/or stdout, depending on set variables '''
        if self.printLog == True:
            print(message)
        if self.writeLog is not None and message != '[Stranger is typing]':
            f = open(self.writeLog, 'a')
            f.write(message + '\n')
            f.close()
        if self.storeLog == True:
            self.log.append(message)
        
    def getEvents(self):
        ''' Get the current conversation "event" from the server, and act accordingly '''
        resp = urllib2.urlopen(EVENTS_URL, self.__encId()).read()
        jsonResp = json.loads(resp)
        if jsonResp not in [None, []]:
            jsonResp = jsonResp[0]
            if jsonResp == 'waiting':
                return
            elif jsonResp[0] == 'strangerDisconnected':
                self.logMessage('[Stranger disconnected]')
                self.connected = False
                if self.doRestart == True:
                    self.restart()
            elif jsonResp[0] == 'gotMessage':
                message = jsonResp[1]
                self.messages[1].append(message)
                self.logMessage('Stranger: %s' % message)
                self.event_Message(message)
            elif jsonResp[0] == 'typing':
                self.logMessage('[Stranger is typing]')
                self.event_Typing()
        
    def __encId(self):
        return urllib.urlencode({'id': self.id})
        
    def sendMessage(self, message):
        ''' Send the supplied message to the Omegle server '''
        postData = urllib.urlencode({'id': self.id, 'msg': message})
        resp = urllib2.urlopen(SEND_URL, postData).read()
        if resp != 'win':
            # 'win' is the standard response returned by the server when
            # a message has been posted successfully
            raise OmegleError('Could not post message.')
        else:
            self.messages[0].append(message)
            self.logMessage('Bot: %s' % message)

    def __setTyping(self, value):
        ''' Function used to set ultimately set the self.typing magic variable '''
        self.__typing = value
        url = {'True': TYPING_URL, 'False': STYPING_URL}[str(value)]
        urllib2.urlopen(url, self.__encId())
        
    def __getattribute__(self, name):
        ''' Used to get the self.typing magic variable '''
        if name == 'typing':
            return self.__typing
        else:
            return object.__getattribute__(self, name)
    
    def __setattr__(self, name, value):
        ''' Used to set the self.typing magic variable '''
        if name == 'typing':
            self.__setTyping(value)
        else:
            self.__dict__[name] = value
            
            
class ChatBot(Bot):
    ''' An AI chatbot extension to the Bot class '''
    
    def __init__(self, ai=None, settings={}, verbose=False, *args, **kwargs ):
        Bot.__init__(self, *args, **kwargs)
        
        self.settings = settings
        self.verbose = verbose
    	self.dummyMode = False
    	self.hasReplied = False
        if ai is None:
            self.ai = self.__mkAI()
        else:
            self.ai = ai
        
    def __mkAI(self):
        ai = aiml.Kernel()
        ai.verbose(self.verbose)
        for property in self.settings:
            # Set the predicates through the AIML class
            ai.setBotPredicate(property,self.settings[property])
        ai.bootstrap(learnFiles=LEARNFILE, commands='LOAD DSAJLKASDJIQIJELQNNCXNCAJKOSNBIABIDUBWUIQ')
        debug('AI Initialized.')
        return ai
        
    def event_Message(self, message):
    	# Check the message for common internet shorthand not checked by the bot.
    	# "Male or female?"
    	if re.match('m(\s*/\s*|\s+|\sor\s)f', message):
    	    message = 'Are you a male or female?'
    	# "Age/sex/location?"
        # XXX: Make this shit work somehow
    	#if re.match('a/+s/+l/+', message):
    	    #message = 'What is your age, sex, and location?'
    	
        r = self.ai.respond(message, self.id)
        if r != '':
            self.hasReplied = True
            return self.reply(r)
    	else:
    	    # If it's the first message in the conversation, just respond "Hello".
    	    if self.hasReplied == False:
                self.hasReplied = True
    		return self.reply('Hello.')
				
    def reply(self, message):
	if self.dummyMode == False:
	    self.typeMessage(message)
    	return message
        
    def typeMessage(self, message):
        typeTime = 0.10 * len(message)
       
        # Simulate 'typing'
        self.typing = True
        debug('Bot is typing for %f sec.' % typeTime)
        time.sleep(typeTime)
        self.typing = False
        
        # Send the message
        self.sendMessage(message)
	return message


def getSettings():
    def loadAI(fname):
        if os.path.isfile(fname):
            # If there's a pickle, load it into the settings
            settings = cPickle.load(open(fname))
            debug('Loaded bot settings from %s.' % fname)
            return settings
        else:
            return None
            
    defProps = ['baseballteam','favoritesong', 'family', 'celebrities', 'feelings', 'phylum', 'president', 'looklike', 'orientation', 'birthplace', 'favoritefood', 'question', 'master', 'location', 'etype', 'friend', 'kingdom', 'favoriteauthor', 'footballteam', 'boyfriend', 'favoriteartist', 'name', 'favoritesport', 'gender', 'favoriteactor', 'celebrity', 'website', 'favoriteband', 'favoritebook', 'favoritecolor', 'sign', 'girlfriend', 'species', 'botmaster', 'forfun', 'favoriteactress', 'emotions', 'religion', 'hockeyteam', 'version', 'build', 'party', 'size', 'email', 'vocabulary', 'birthday', 'favoritemovie', 'nationality', 'ethics', 'friends', 'class', 'talkabout', 'language', 'age', 'kindmusic', 'genus', 'order', 'wear']
    
    # Gather AI data:
    settings = loadAI(USR_SETTINGS)
    if settings is None:
        settings = loadAI(DEF_SETTINGS)
        if settings is None:
            settings = {}
            # If there's no pickle, offer to load it manually
            cmd = raw_input('Bot predicate settings not found. Manual entry? [y/N] ')
            if cmd.upper() == 'Y':
                n, m = 1, len(defProps)
                # Then just cycle through defProps and set the dictionary up
                for question in defProps:
                    settings[question] = raw_input('[%d/%d] %s? ' % (n,m,question))
                    n += 1
                # Dump that mofo and you're good to go.
                pickle.dump(settings,open(f,'w'))
                print('Bot predicate settings saved to %s. Exclude this file if you redistribute this project.' % f)
            else:
                # Seriously, not having *any* bot predicates is going to make your shit look all retarded.
                print('Warning: bot predicate settings do not exist. This will cause some responses to have blank spaces.')
    return settings
        
def main(logfile=None):
    settings = getSettings()
    ai = None
    
    while True:
        bot = ChatBot(writeLog=logfile, printLog=True, verbose=True, settings=settings, ai=ai)
        bot.start()
        
        while bot.connected == True:
            try:
                time.sleep(0.1)
            except OmegleError, err:
                bot.connected = False
                sys.stderr.write(str(err))
                sys.exit(1)
            except KeyboardInterrupt:
                bot.stop()
                sys.exit(0)
        ai = bot.ai
            

if __name__ == '__main__':
    if len(sys.argv) > 1:
        logfile = sys.argv[1]
    else:
        logfile = 'logs/%s' % time.strftime('%m%d%Y-%H%M%S')
        
    main(logfile)

