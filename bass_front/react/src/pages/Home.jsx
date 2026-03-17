import { useNavigate } from 'react-router-dom';

import guitarImg from '../images/음악제작버튼.png'; 
import searchImg from '../images/음악검색버튼.png';

function Home() {
  const navigate = useNavigate();

  return (
    <div style={{ padding: '80px 20px', textAlign: 'center', minHeight: '100vh', backgroundColor: '#fff' }}>
      <h2 style={{ marginBottom: '60px', fontSize: '2.2rem', fontWeight: 'bold' }}>
        어떤 작업을 하시겠습니까?
      </h2>
      
      <div style={{ display: 'flex', justifyContent: 'center', gap: '40px', flexWrap: 'wrap' }}>
        
        {/* 노래 제작 카드 */}
        <div 
          onClick={() => navigate('/create')}
          style={cardStyle}
          onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
          onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
        >
          {/* ✅ 여기서 이미지의 크기를 결정합니다 (180px로 증량) */}
          <div style={iconWrapperStyle}>
            <img src={guitarImg} alt="노래 제작" style={imageStyle} />
          </div>
          <h3 style={titleStyle}>노래 제작</h3>
          <p style={descStyle}>YouTube URL로<br/>새로운 악보 생성</p>
        </div>

        {/* 노래 검색 카드 */}
        <div 
          onClick={() => navigate('/search')}
          style={cardStyle}
          onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
          onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
        >
          <div style={iconWrapperStyle}>
            <img src={searchImg} alt="노래 검색" style={imageStyle} />
          </div>
          <h3 style={titleStyle}>노래 검색</h3>
          <p style={descStyle}>이미 생성된<br/>악보 찾아보기</p>
        </div>

      </div>
    </div>
  );
}


const cardStyle = {
  width: '350px',          
  padding: '50px 20px', 
  border: '2px solid #000', 
  borderRadius: '30px',
  cursor: 'pointer', 
  transition: 'transform 0.2s ease-in-out', 
  textAlign: 'center',
  backgroundColor: '#fff',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center'
};

const iconWrapperStyle = {
  width: '180px',           
  height: '180px',          
  marginBottom: '20px',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  overflow: 'hidden'        
};

const imageStyle = {
  width: '100%',           
  height: '100%',           
  objectFit: 'contain'     
};

const titleStyle = {
  fontSize: '1.7rem',
  margin: '10px 0',
  fontWeight: 'bold'
};

const descStyle = {
  fontSize: '1.1rem',
  color: '#555',
  lineHeight: '1.5'
};

export default Home;