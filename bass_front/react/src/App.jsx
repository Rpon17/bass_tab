import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing.jsx'; 
import Home from './pages/Home.jsx';       
import Search from './pages/Search.jsx';   
import Player from './pages/Player.jsx';
import Create from './pages/Create.jsx'; 

function App() {
  return (
    <BrowserRouter>
      <div style={{ fontFamily: 'sans-serif', minHeight: '100vh' }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/home" element={<Home />} />
          <Route path="/create" element={<Create />} />
          <Route path="/search" element={<Search />} />
          <Route path="/player/:song_id" element={<Player />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;