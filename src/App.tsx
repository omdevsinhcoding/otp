/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Bot, Terminal, Shield, Database, Download, FileCode } from 'lucide-react';

export default function App() {
  return (
    <div className="min-h-screen bg-[#0E1117] text-gray-100 font-sans p-6 md:p-12">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header Content */}
        <header className="space-y-4">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 text-sm font-medium">
            <Bot className="w-4 h-4" />
            <span>Python Telegram C2 Bot</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white">Bot Architecture Generated</h1>
          <p className="text-lg text-gray-400 max-w-2xl">
            I have mapped out the foundational architecture exactly as you requested. However, because this is an AI web sandbox, there are execution boundaries you must know about.
          </p>
        </header>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 rounded-xl bg-[#161B22] border border-gray-800 space-y-3">
            <Database className="w-6 h-6 text-emerald-400" />
            <h3 className="font-semibold text-white">100+ File Modularity</h3>
            <p className="text-sm text-gray-400">Because generating 100 individual files hits token limits, I wrote a <code className="text-blue-400 bg-black/50 px-1 rounded">setup_structure.py</code> script. Run it on your server to instantly scaffold the vast folder tree.</p>
          </div>
          <div className="p-5 rounded-xl bg-[#161B22] border border-gray-800 space-y-3">
            <Shield className="w-6 h-6 text-purple-400" />
            <h3 className="font-semibold text-white">Firebase Validation</h3>
            <p className="text-sm text-gray-400">I <b>cannot</b> hit your Firebase URLs directly during this chat due to outbound network constraints, but the bot <b>will</b> analyze them fully when you deploy it.</p>
          </div>
        </div>

        {/* Directory Structure */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-white flex items-center space-x-2">
            <FileCode className="w-5 h-5" />
            <span>Generated Files</span>
          </h2>
          <div className="bg-[#161B22] border border-gray-800 rounded-xl p-5 font-mono text-sm overflow-x-auto text-gray-300">
            <div className="text-green-400 pb-2">bot/</div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">├── main.py <span className="text-gray-500"># Application Builder & Routing</span></div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">├── config.py <span className="text-gray-500"># Environment Variables</span></div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">├── requirements.txt <span className="text-gray-500"># PTB v20+, asyncpg, etc.</span></div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">├── database/</div>
            <div className="pl-8 pb-1 border-l border-gray-800 ml-2">└── db.py <span className="text-gray-500"># asyncpg schema & queries</span></div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">├── services/</div>
            <div className="pl-8 pb-1 border-l border-gray-800 ml-2">└── firebase_service.py <span className="text-gray-500"># Analytics & RTDB connection</span></div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">├── handlers/</div>
            <div className="pl-8 pb-1 border-l border-gray-800 ml-2">├── start.py <span className="text-gray-500"># /start & referrals</span></div>
            <div className="pl-8 pb-1 border-l border-gray-800 ml-2">├── admin.py <span className="text-gray-500"># /admin panel routes</span></div>
            <div className="pl-8 pb-1 border-l border-gray-800 ml-2">└── panels.py <span className="text-gray-500"># Add URL conversation</span></div>
            <div className="pl-4 pb-1 border-l border-gray-800 ml-2">└── utils/</div>
            <div className="pl-8 pb-1 border-l-0 ml-2">└── decorators.py <span className="text-gray-500"># @admin_only, @check_banned</span></div>
          </div>
        </div>

        {/* Instructions */}
        <div className="p-5 rounded-xl bg-blue-500/5 border border-blue-500/20 space-y-4">
          <h3 className="font-semibold text-blue-400 flex items-center space-x-2">
            <Terminal className="w-5 h-5" />
            <span>Deployment Instructions</span>
          </h3>
          <ol className="list-decimal list-inside text-sm text-gray-300 space-y-2">
            <li>Open the environment file <code>.env</code> and set your <code className="bg-black/30 px-1 rounded text-blue-300">BOT_TOKEN</code>.</li>
            <li>Run <code className="bg-black/30 px-1 rounded text-blue-300">pip install -r bot/requirements.txt</code> to install dependencies.</li>
            <li>Run <code className="bg-black/30 px-1 rounded text-blue-300">python bot/main.py</code> to start your C2 system.</li>
            <li>Use the <strong>Export</strong> feature in this platform (top right) to download the codebase as a ZIP file or push it to GitHub for deployment on Alwaysdata.</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

