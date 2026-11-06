import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { Provider } from "./components/ui/provider"
import { registerServiceWorker } from './lib/pwa';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <Provider>
    <React.StrictMode>
      <App />
    </React.StrictMode>
  </Provider>
);

registerServiceWorker();
