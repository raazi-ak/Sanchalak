import React from 'react';
import { ConversationProgress } from '../types';

interface ProgressTrackerProps {
  progress?: ConversationProgress;
}

const ProgressTracker: React.FC<ProgressTrackerProps> = ({ progress }) => {
  if (!progress) return null;

  const stages = [
    { key: 'basicInfo', label: 'Basic Info', color: 'bg-blue-500' },
    { key: 'familyMembers', label: 'Family', color: 'bg-green-500' },
    { key: 'exclusionCriteria', label: 'Exclusions', color: 'bg-yellow-500' },
    { key: 'specialProvisions', label: 'Special', color: 'bg-purple-500' }
  ];

  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-800">Progress</h3>
        <span className="text-2xl font-bold text-green-600">
          {progress.overallPercentage}%
        </span>
      </div>
      
      <div className="space-y-3">
        {stages.map((stage) => {
          const stageProgress = progress[stage.key as keyof ConversationProgress] as any;
          const percentage = stageProgress ? (stageProgress.collected / stageProgress.total) * 100 : 0;
          
          return (
            <div key={stage.key} className="flex items-center space-x-3">
              <div className="w-4 h-4 rounded-full bg-gray-200 flex-shrink-0">
                {percentage >= 100 && (
                  <div className={`w-4 h-4 rounded-full ${stage.color} flex items-center justify-center`}>
                    <svg className="w-2 h-2 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
              </div>
              <div className="flex-1">
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700">{stage.label}</span>
                  <span className="text-gray-500">
                    {stageProgress?.collected || 0}/{stageProgress?.total || 0}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full ${stage.color} progress-bar`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProgressTracker; 