import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing.jsx'; 
import Home from './pages/Home.jsx';       
import Search from './pages/Search.jsx';   
import Player from './pages/Player.jsx';
import Create from './pages/Create.jsx'; 

// ✅ 실제 폴더에 있는 파일명(언더바와 철자 tt)과 100% 일치시켰습니다.
import CreateYoutube from './pages/Create_youtube.jsx'; 
import CreateUpload from './pages/Create_upload.jsx';   
import Waiting from './pages/Waiting.jsx'; 

function App() {
  return (
    <BrowserRouter>
      <div style={{ fontFamily: 'sans-serif', minHeight: '100vh' }}>
        <Routes>
          {/* 1. 시작 및 홈 화면 */}
          <Route path="/" element={<Landing />} />
          <Route path="/home" element={<Home />} />
          
          {/* 2. 악보 제작 관련 경로 */}
          <Route path="/create" element={<Create />} />
          <Route path="/create/youtube" element={<CreateYoutube />} />
          <Route path="/create/upload" element={<CreateUpload />} />
          
          {/* 3. 로딩/대기 화면 */}
          <Route path="/waiting" element={<Waiting />} />
          
          {/* 4. 검색 및 플레이어 */}
          <Route path="/search" element={<Search />} />
          <Route path="/player/:song_id" element={<Player />} />
          
          {/* 5. 잘못된 경로 접근 시 홈으로 리다이렉트 */}
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;