/**
 * 浏览器内置语音识别（Web Speech API）
 * Chrome / Edge 可用，无需 OpenAI Key；需联网，由浏览器厂商提供识别服务。
 */
export function isBrowserSpeechSupported() {
  return typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)
}

export function createBrowserSpeechRecognizer({ lang = 'zh-CN', onPartial, onError } = {}) {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Ctor) return null

  const recognition = new Ctor()
  recognition.lang = lang
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 1

  let finalText = ''
  let interimText = ''

  recognition.onresult = (event) => {
    interimText = ''
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const piece = event.results[i][0]?.transcript || ''
      if (event.results[i].isFinal) {
        finalText += piece
      } else {
        interimText += piece
      }
    }
    if (onPartial) onPartial({ finalText, interimText, display: (finalText + interimText).trim() })
  }

  recognition.onerror = (event) => {
    if (onError) onError(event.error || 'unknown')
  }

  return {
    start() {
      finalText = ''
      interimText = ''
      recognition.start()
    },
    stop() {
      recognition.stop()
    },
    abort() {
      recognition.abort()
    },
    getFinalText() {
      return (finalText + interimText).trim()
    },
    recognition
  }
}
