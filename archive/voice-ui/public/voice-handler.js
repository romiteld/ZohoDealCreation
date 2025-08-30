// Voice Handler - Azure Speech SDK Integration
class VoiceHandler {
  constructor() {
    this.recognizer = null;
    this.synthesizer = null;
    this.isListening = false;
    this.isContinuous = false;
    this.confidence = 0;
    this.lastTranscript = '';
    
    // Event callbacks
    this.onTranscriptUpdate = null;
    this.onConfidenceUpdate = null;
    this.onVoiceCommand = null;
    this.onListeningStateChange = null;
    this.onError = null;
    this.onInitialized = null;
    
    this.initializeSpeechSDK();
  }

  async initializeSpeechSDK() {
    try {
      this.log('Initializing Azure Speech SDK...');
      
      if (typeof SpeechSDK === 'undefined') {
        this.handleError('Azure Speech SDK not loaded. Please check your internet connection and refresh the page.');
        return;
      }

      const config = window.WellConfig.speech;
      this.log('Speech config loaded:', config.region);
      
      // Create speech config
      const speechConfig = SpeechSDK.SpeechConfig.fromSubscription(config.key, config.region);
      speechConfig.speechRecognitionLanguage = config.language;
      speechConfig.enableDictation();
      
      // Create audio config
      const audioConfig = SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
      
      // Create speech recognizer
      this.recognizer = new SpeechSDK.SpeechRecognizer(speechConfig, audioConfig);
      
      // Set up event handlers
      this.setupRecognizerEvents();
      
      // Create speech synthesizer for feedback
      this.synthesizer = new SpeechSDK.SpeechSynthesizer(speechConfig);
      
      this.log('Speech SDK initialized successfully');
      
      // Request microphone permission
      await this.requestMicrophonePermission();
      
      // Notify that initialization is complete
      if (this.onInitialized) {
        this.onInitialized(true);
      }
      
    } catch (error) {
      this.log('Failed to initialize Speech SDK:', error);
      this.handleError('Failed to initialize voice recognition. Please check your microphone permissions and refresh the page.');
      
      // Notify that initialization failed
      if (this.onInitialized) {
        this.onInitialized(false);
      }
    }
  }

  setupRecognizerEvents() {
    if (!this.recognizer) return;

    // Recognizing event (interim results)
    this.recognizer.recognizing = (s, e) => {
      this.log('Recognizing:', e.result.text);
      this.updateTranscript(e.result.text, false);
      this.updateConfidence(e.result.reason === SpeechSDK.ResultReason.RecognizingSpeech ? 0.7 : 0.3);
    };

    // Recognized event (final results)
    this.recognizer.recognized = (s, e) => {
      if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
        this.log('Recognized:', e.result.text);
        this.updateTranscript(e.result.text, true);
        this.updateConfidence(0.9);
        this.processVoiceCommand(e.result.text);
      } else if (e.result.reason === SpeechSDK.ResultReason.NoMatch) {
        this.log('No speech recognized');
        this.updateConfidence(0);
      }
    };

    // Session started
    this.recognizer.sessionStarted = (s, e) => {
      this.log('Recognition session started');
      this.isListening = true;
      this.notifyListeningStateChange();
    };

    // Session stopped
    this.recognizer.sessionStopped = (s, e) => {
      this.log('Recognition session stopped');
      this.isListening = false;
      this.notifyListeningStateChange();
    };

    // Canceled event
    this.recognizer.canceled = (s, e) => {
      this.log('Recognition canceled:', e.reason);
      if (e.reason === SpeechSDK.CancellationReason.Error) {
        this.handleError(`Speech recognition error: ${e.errorDetails}`);
      }
      this.isListening = false;
      this.notifyListeningStateChange();
    };
  }

  async requestMicrophonePermission() {
    try {
      this.log('Requesting microphone permission...');
      
      // Check if getUserMedia is available
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        this.handleError('This browser does not support microphone access. Please use a modern browser like Chrome, Firefox, or Edge.');
        return false;
      }

      // Request microphone access - this will trigger the browser's permission dialog
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000
        } 
      });
      
      // Stop the stream immediately as we just needed permission
      stream.getTracks().forEach(track => track.stop());
      
      this.log('Microphone permission granted');
      return true;
    } catch (error) {
      this.log('Microphone permission error:', error);
      
      if (error.name === 'NotAllowedError') {
        this.handleError('Microphone access denied. Please click the microphone icon in your browser\'s address bar and allow access, then refresh the page.');
      } else if (error.name === 'NotFoundError') {
        this.handleError('No microphone found. Please connect a microphone and refresh the page.');
      } else if (error.name === 'NotReadableError') {
        this.handleError('Microphone is already in use by another application. Please close other applications using the microphone and refresh.');
      } else {
        this.handleError(`Microphone access failed: ${error.message}. Please check your browser settings and refresh the page.`);
      }
      return false;
    }
  }

  startListening(continuous = false) {
    if (!this.recognizer) {
      this.handleError('Voice recognition not initialized');
      return;
    }

    if (this.isListening) {
      this.log('Already listening');
      return;
    }

    try {
      this.isContinuous = continuous;
      
      if (continuous) {
        this.recognizer.startContinuousRecognitionAsync(
          () => {
            this.log('Continuous recognition started');
            this.isListening = true;
            this.notifyListeningStateChange();
          },
          (error) => {
            this.log('Failed to start continuous recognition:', error);
            this.handleError('Failed to start voice recognition');
          }
        );
      } else {
        this.recognizer.recognizeOnceAsync(
          (result) => {
            this.log('Single recognition completed');
            this.isListening = false;
            this.notifyListeningStateChange();
          },
          (error) => {
            this.log('Failed to start recognition:', error);
            this.handleError('Failed to start voice recognition');
            this.isListening = false;
            this.notifyListeningStateChange();
          }
        );
      }
    } catch (error) {
      this.log('Error starting recognition:', error);
      this.handleError('Failed to start voice recognition');
    }
  }

  stopListening() {
    if (!this.recognizer || !this.isListening) {
      return;
    }

    try {
      if (this.isContinuous) {
        this.recognizer.stopContinuousRecognitionAsync(
          () => {
            this.log('Continuous recognition stopped');
            this.isListening = false;
            this.notifyListeningStateChange();
          },
          (error) => {
            this.log('Failed to stop continuous recognition:', error);
            this.isListening = false;
            this.notifyListeningStateChange();
          }
        );
      } else {
        // Single recognition will stop automatically
        this.isListening = false;
        this.notifyListeningStateChange();
      }
    } catch (error) {
      this.log('Error stopping recognition:', error);
      this.isListening = false;
      this.notifyListeningStateChange();
    }
  }

  toggleListening(continuous = false) {
    if (this.isListening) {
      this.stopListening();
    } else {
      this.startListening(continuous);
    }
  }

  async speak(text, priority = 'normal') {
    if (!this.synthesizer || !window.WellConfig.features.voiceFeedback) {
      return;
    }

    try {
      const ssml = this.createSSML(text, priority);
      
      this.synthesizer.speakSsmlAsync(
        ssml,
        (result) => {
          if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
            this.log('Speech synthesis completed');
          }
        },
        (error) => {
          this.log('Speech synthesis failed:', error);
        }
      );
    } catch (error) {
      this.log('Error in speech synthesis:', error);
    }
  }

  createSSML(text, priority = 'normal') {
    const config = window.WellConfig.speech.synthesis;
    let rate = config.rate;
    let pitch = config.pitch;
    
    // Adjust for priority
    if (priority === 'urgent') {
      rate = '+10%';
      pitch = '+5%';
    } else if (priority === 'low') {
      rate = '-10%';
      pitch = '-5%';
    }

    return `
      <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
        <voice name="${config.voice}">
          <prosody rate="${rate}" pitch="${pitch}">
            ${text}
          </prosody>
        </voice>
      </speak>
    `;
  }

  processVoiceCommand(transcript) {
    if (!transcript || transcript.trim().length === 0) {
      return;
    }

    const normalizedTranscript = transcript.toLowerCase().trim();
    const commands = window.WellConfig.commands;
    
    this.log('Processing voice command:', normalizedTranscript);
    
    // Check for specific commands
    let commandType = null;
    let commandData = { transcript: normalizedTranscript };
    
    // Email processing commands
    if (this.matchesCommand(normalizedTranscript, commands.processEmail)) {
      commandType = 'processEmail';
    } else if (this.matchesCommand(normalizedTranscript, commands.approveExtraction)) {
      commandType = 'approveExtraction';
    } else if (this.matchesCommand(normalizedTranscript, commands.rejectExtraction)) {
      commandType = 'rejectExtraction';
    } else if (this.matchesCommand(normalizedTranscript, commands.editField)) {
      commandType = 'editField';
      // Extract field name and value if possible
      commandData.fieldInfo = this.extractFieldEdit(normalizedTranscript);
    }
    
    // Navigation commands
    else if (this.matchesCommand(normalizedTranscript, commands.nextEmail)) {
      commandType = 'nextEmail';
    } else if (this.matchesCommand(normalizedTranscript, commands.previousEmail)) {
      commandType = 'previousEmail';
    } else if (this.matchesCommand(normalizedTranscript, commands.showQueue)) {
      commandType = 'showQueue';
    } else if (this.matchesCommand(normalizedTranscript, commands.showMetrics)) {
      commandType = 'showMetrics';
    }
    
    // Settings commands
    else if (this.matchesCommand(normalizedTranscript, commands.openSettings)) {
      commandType = 'openSettings';
    } else if (this.matchesCommand(normalizedTranscript, commands.toggleMode)) {
      commandType = 'toggleMode';
    }
    
    // Default to freeform command if no specific match
    else {
      commandType = 'freeform';
    }
    
    // Notify command handler
    if (this.onVoiceCommand) {
      this.onVoiceCommand(commandType, commandData);
    }
  }

  matchesCommand(transcript, commandList) {
    return commandList.some(command => 
      transcript.includes(command.toLowerCase()) ||
      this.fuzzyMatch(transcript, command.toLowerCase())
    );
  }

  fuzzyMatch(str1, str2, threshold = 0.8) {
    // Simple fuzzy matching based on common words
    const words1 = str1.split(' ');
    const words2 = str2.split(' ');
    
    const commonWords = words1.filter(word => 
      words2.some(word2 => word.includes(word2) || word2.includes(word))
    );
    
    const similarity = commonWords.length / Math.max(words1.length, words2.length);
    return similarity >= threshold;
  }

  extractFieldEdit(transcript) {
    // Extract field name and new value from voice command
    // Examples: "change name to John Smith", "edit company to Acme Corp"
    const patterns = [
      /(?:change|edit|update|modify)\s+(\w+)\s+to\s+(.+)/i,
      /set\s+(\w+)\s+to\s+(.+)/i,
      /(\w+)\s+should\s+be\s+(.+)/i
    ];
    
    for (const pattern of patterns) {
      const match = transcript.match(pattern);
      if (match) {
        return {
          field: match[1].toLowerCase(),
          value: match[2].trim()
        };
      }
    }
    
    return null;
  }

  updateTranscript(transcript, isFinal) {
    this.lastTranscript = transcript;
    if (this.onTranscriptUpdate) {
      this.onTranscriptUpdate(transcript, isFinal);
    }
  }

  updateConfidence(confidence) {
    this.confidence = confidence;
    if (this.onConfidenceUpdate) {
      this.onConfidenceUpdate(confidence);
    }
  }

  notifyListeningStateChange() {
    if (this.onListeningStateChange) {
      this.onListeningStateChange(this.isListening, this.isContinuous);
    }
  }

  handleError(message) {
    this.log('Error:', message);
    if (this.onError) {
      this.onError(message);
    }
  }

  log(...args) {
    if (window.WellConfig.debug.enableLogging && window.WellConfig.debug.logToConsole) {
      console.log('[VoiceHandler]', ...args);
    }
  }

  // Cleanup
  dispose() {
    if (this.recognizer) {
      if (this.isListening) {
        this.stopListening();
      }
      this.recognizer.close();
      this.recognizer = null;
    }
    
    if (this.synthesizer) {
      this.synthesizer.close();
      this.synthesizer = null;
    }
  }

  // Getters
  get isInitialized() {
    return this.recognizer !== null && this.synthesizer !== null;
  }

  get currentTranscript() {
    return this.lastTranscript;
  }

  get currentConfidence() {
    return this.confidence;
  }

  get listeningState() {
    return {
      isListening: this.isListening,
      isContinuous: this.isContinuous,
      confidence: this.confidence,
      transcript: this.lastTranscript
    };
  }
}

// Export for use in main app
window.VoiceHandler = VoiceHandler;