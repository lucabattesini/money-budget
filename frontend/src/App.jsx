import './styles/index.css';
import {BrowserRouter, Routes, Route} from "react-router-dom";
import Home from "./pages/home"
import CreateAccount from './pages/create_account';

function App() {
  return (
    <BrowserRouter>
      <Routes>
          <Route path='/' element={<Home />}/>
          <Route path='create-account' element={<CreateAccount/>}/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
