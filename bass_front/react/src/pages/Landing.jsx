import { useNavigate } from 'react-router-dom';

function Landing() {
  const navigate = useNavigate();

  return (
    <div style={{ 
      height: '100vh', display: 'flex', flexDirection: 'column', 
      justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' 
    }}>
      <h1 style={{ fontSize: '3rem', marginBottom: '20px' }}>Bass Master AI</h1>
      <p style={{ color: '#666', marginBottom: '40px' }}>당신만의 베이스 악보와 함께 꿈을 연주하세요</p>
      <button 
        onClick={() => navigate('/home')}
        style={{
          padding: '15px 40px', fontSize: '1.2rem', cursor: 'pointer',
          backgroundColor: '#000', color: '#fff', border: 'none', borderRadius: '30px'
        }}
      >
        시작하기
      </button>
    </div>
  );
}

export default Landing;