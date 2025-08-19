import './styles/index.css';
import {BrowserRouter, Routes, Route} from "react-router-dom";
import Home from "./pages/home"
import Login from './pages/login';
import CreateAccount from './pages/create-account';

function App() {
  return (
    <BrowserRouter>
      <Routes>
          <Route path='/' element={ <Home/> }/>
          <Route path='/login' element={ <Login/> }/>
          <Route path='/create-account' element={ <CreateAccount/> }/>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
