import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/index.css';
import App from './App';
import { Provider } from "./components/ui/provider"

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <Provider>
    <React.StrictMode>
      <App />
    </React.StrictMode>
  </Provider>
);