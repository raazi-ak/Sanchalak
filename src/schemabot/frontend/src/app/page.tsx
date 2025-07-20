'use client'

import React, { useState, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { request, gql } from 'graphql-request'

// GraphQL endpoint
const GRAPHQL_ENDPOINT = 'http://localhost:8003/graphql'

// GraphQL queries and mutations
const START_CONVERSATION = gql`
  mutation StartConversation($input: StartConversationInput!) {
    startConversation(input: $input) {
      id
      stage
      messages(limit: 1) {
        content
        role
        timestamp
      }
      progress {
        overallPercentage
        basicInfo {
          collected
          total
          percentage
          isComplete
        }
        familyMembers {
          collected
          total
          percentage
          isComplete
        }
        exclusionCriteria {
          collected
          total
          percentage
          isComplete
        }
        specialProvisions {
          collected
          total
          percentage
          isComplete
        }
      }
    }
  }
`

const SEND_MESSAGE = gql`
  mutation SendMessage($input: SendMessageInput!) {
    sendMessage(input: $input) {
      id
      content
      role
      timestamp
    }
  }
`

const GET_CONVERSATION = gql`
  query GetConversation($sessionId: String!) {
    conversation(sessionId: $sessionId) {
      id
      stage
      isComplete
      progress {
        overallPercentage
        basicInfo {
          collected
          total
          percentage
          isComplete
        }
        familyMembers {
          collected
          total
          percentage
          isComplete
        }
        exclusionCriteria {
          collected
          total
          percentage
          isComplete
        }
        specialProvisions {
          collected
          total
          percentage
          isComplete
        }
      }
      farmerData {
        basicInfo
        familyMembers
        exclusionData
        specialProvisions
        schemeCode
        completedAt
      }
    }
  }
`

const GET_AVAILABLE_SCHEMES = gql`
  query GetAvailableSchemes {
    availableSchemes
  }
`

// Types
interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface Scheme {
  scheme_code: string
  scheme_name: string
  description: string
}

interface Progress {
  overallPercentage: number
  basicInfo: {
    collected: number
    total: number
    percentage: number
    isComplete: boolean
  }
  familyMembers: {
    collected: number
    total: number
    percentage: number
    isComplete: boolean
  }
  exclusionCriteria: {
    collected: number
    total: number
    percentage: number
    isComplete: boolean
  }
  specialProvisions: {
    collected: number
    total: number
    percentage: number
    isComplete: boolean
  }
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string>('')
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [selectedScheme, setSelectedScheme] = useState<Scheme | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [currentStage, setCurrentStage] = useState('')
  const [isComplete, setIsComplete] = useState(false)
  const [farmerData, setFarmerData] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    loadSchemes()
  }, [])

  const loadSchemes = async () => {
    try {
      const data = await request(GRAPHQL_ENDPOINT, GET_AVAILABLE_SCHEMES) as { availableSchemes: Array<{ scheme_code: string; name: string; description: string }> }
      const schemes = Array.isArray(data.availableSchemes) ? data.availableSchemes : []
      const formattedSchemes = schemes.map((scheme: { scheme_code: string; name: string; description: string }) => ({
        scheme_code: scheme.scheme_code,
        scheme_name: scheme.name || scheme.scheme_code.toUpperCase(),
        description: scheme.description || `Apply for ${scheme.name || 'this scheme'}`
      }))
      setSchemes(formattedSchemes)
    } catch (error) {
      console.error('Error loading schemes:', error)
      // Fallback schemes
      setSchemes([
        { scheme_code: 'pm-kisan', scheme_name: 'PM-KISAN', description: 'Farmer income support scheme' }
      ])
    }
  }

  const selectScheme = async (scheme: Scheme) => {
    setSelectedScheme(scheme)
    setIsLoading(true)
    
    try {
      const data = await request(GRAPHQL_ENDPOINT, START_CONVERSATION, {
        input: { schemeCode: scheme.scheme_code }
      }) as { startConversation: { id: string; stage: string; messages: Array<{ content: string; role: string; timestamp: string }>; progress: Progress } }
      
      const conversation = data.startConversation
      
      // Set session ID from GraphQL response
      setSessionId(conversation.id)
      
      // Add initial assistant message
      if (conversation.messages && conversation.messages.length > 0) {
        const assistantMessage: Message = {
          id: uuidv4(),
          type: 'assistant',
          content: conversation.messages[0].content,
          timestamp: conversation.messages[0].timestamp
        }
        setMessages([assistantMessage])
      }
      
      setProgress(conversation.progress)
      setCurrentStage(conversation.stage)
      
    } catch (error) {
      console.error('Error starting conversation:', error)
      // Fallback message
      const fallbackMessage: Message = {
        id: uuidv4(),
        type: 'assistant',
        content: `Hello! I'm here to help you with your ${scheme.scheme_name} application. Let's start with your basic information. What's your name?`,
        timestamp: new Date().toISOString()
      }
      setMessages([fallbackMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || !sessionId) return

    const userMessage: Message = {
      id: uuidv4(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)

    try {
      const data = await request(GRAPHQL_ENDPOINT, SEND_MESSAGE, {
        input: {
          sessionId: sessionId,
          content: inputMessage
        }
      }) as { sendMessage: { id: string; content: string; timestamp: string } }
      
      const assistantResponse = data.sendMessage
      
      const assistantMessage: Message = {
        id: assistantResponse.id,
        type: 'assistant',
        content: assistantResponse.content,
        timestamp: assistantResponse.timestamp
      }
      
      setMessages(prev => [...prev, assistantMessage])
      
      // Get updated conversation state
      const conversationData = await request(GRAPHQL_ENDPOINT, GET_CONVERSATION, {
        sessionId: sessionId
      }) as { conversation: { progress: Progress; stage: string; isComplete: boolean; farmerData?: Record<string, unknown> } }
      
      if (conversationData.conversation) {
        setProgress(conversationData.conversation.progress)
        setCurrentStage(conversationData.conversation.stage)
        setIsComplete(conversationData.conversation.isComplete)
        if (conversationData.conversation.farmerData) {
          setFarmerData(conversationData.conversation.farmerData)
        }
      }
      
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        id: uuidv4(),
        type: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (!selectedScheme) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gray-800 mb-4">
              🌾 SANCHALAK
            </h1>
            <p className="text-lg text-gray-600">
              Government Scheme Application Assistant
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {schemes.map((scheme) => (
              <div
                key={scheme.scheme_code}
                className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer border-l-4 border-green-500"
                onClick={() => selectScheme(scheme)}
              >
                <h3 className="text-xl font-semibold text-gray-800 mb-2">
                  {scheme.scheme_name}
                </h3>
                <p className="text-gray-600 mb-4">
                  {scheme.description}
                </p>
                <button className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 transition-colors">
                  Start Application →
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h1 className="text-2xl font-bold text-gray-800">
                🌾 {selectedScheme.scheme_name} Assistant
              </h1>
              <span className="text-sm text-gray-500">
                Stage: {currentStage.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <button
              onClick={() => {
                setSelectedScheme(null)
                setMessages([])
                setSessionId('')
                setProgress(null)
                setIsComplete(false)
                setFarmerData(null)
              }}
              className="text-gray-500 hover:text-gray-700"
            >
              ← Back to Schemes
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-4">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Progress Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-md p-6 sticky top-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                Progress
              </h3>
              
              {progress && (
                <div className="space-y-4">
                  {/* Overall Progress */}
                  <div>
                    <div className="flex justify-between text-sm text-gray-600 mb-1">
                      <span>Overall</span>
                      <span>{Math.round(progress.overallPercentage)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-green-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${progress.overallPercentage}%` }}
                      ></div>
                    </div>
                  </div>

                  {/* Stage Progress */}
                  <div className="space-y-3">
                    <div className={`p-3 rounded-md ${progress.basicInfo.isComplete ? 'bg-green-100' : 'bg-gray-100'}`}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Basic Info</span>
                        <span>{progress.basicInfo.collected}/{progress.basicInfo.total}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div 
                          className={`h-1 rounded-full transition-all duration-300 ${progress.basicInfo.isComplete ? 'bg-green-600' : 'bg-blue-500'}`}
                          style={{ width: `${progress.basicInfo.percentage}%` }}
                        ></div>
                      </div>
                    </div>

                    <div className={`p-3 rounded-md ${progress.familyMembers.isComplete ? 'bg-green-100' : 'bg-gray-100'}`}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Family Info</span>
                        <span>{progress.familyMembers.collected}/{progress.familyMembers.total}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div 
                          className={`h-1 rounded-full transition-all duration-300 ${progress.familyMembers.isComplete ? 'bg-green-600' : 'bg-blue-500'}`}
                          style={{ width: `${progress.familyMembers.percentage}%` }}
                        ></div>
                      </div>
                    </div>

                    <div className={`p-3 rounded-md ${progress.exclusionCriteria.isComplete ? 'bg-green-100' : 'bg-gray-100'}`}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Eligibility</span>
                        <span>{progress.exclusionCriteria.collected}/{progress.exclusionCriteria.total}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div 
                          className={`h-1 rounded-full transition-all duration-300 ${progress.exclusionCriteria.isComplete ? 'bg-green-600' : 'bg-blue-500'}`}
                          style={{ width: `${progress.exclusionCriteria.percentage}%` }}
                        ></div>
                      </div>
                    </div>

                    <div className={`p-3 rounded-md ${progress.specialProvisions.isComplete ? 'bg-green-100' : 'bg-gray-100'}`}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Special Info</span>
                        <span>{progress.specialProvisions.collected}/{progress.specialProvisions.total}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div 
                          className={`h-1 rounded-full transition-all duration-300 ${progress.specialProvisions.isComplete ? 'bg-green-600' : 'bg-blue-500'}`}
                          style={{ width: `${progress.specialProvisions.percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Chat Panel */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow-md h-[calc(100vh-200px)] flex flex-col">
              {/* Messages */}
              <div className="flex-1 p-6 overflow-y-auto">
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                          message.type === 'user'
                            ? 'bg-green-600 text-white'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{message.content}</p>
                        <p className="text-xs mt-1 opacity-70">
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                  ))}
                  
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                          <span>Assistant is typing...</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Input */}
              <div className="border-t p-4">
                {isComplete && farmerData ? (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <h3 className="text-lg font-semibold text-green-800 mb-2">
                      ✅ Application Complete!
                    </h3>
                    <p className="text-green-700 mb-3">
                      Your {selectedScheme.scheme_name} application has been successfully collected.
                    </p>
                    <button 
                      onClick={() => console.log('Farmer Data:', farmerData)}
                      className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 transition-colors"
                    >
                      Download Application Data
                    </button>
                  </div>
                ) : (
                  <div className="flex space-x-4">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Type your message..."
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                      disabled={isLoading}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={isLoading || !inputMessage.trim()}
                      className="bg-green-600 text-white px-6 py-2 rounded-md hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Send
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
