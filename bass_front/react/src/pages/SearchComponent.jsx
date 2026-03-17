import { useState } from 'react';

function SearchComponent() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  const handleSearch = async (e) => {
    const value = e.target.value;
    setQuery(value);

    if (value.length < 2) {
      setResults([]);
      return;
    }

    try {
      // 백엔드의 검색 엔드포인트 호출
      const response = await fetch(`http://localhost:8000/v1/songs/search?q=${encodeURIComponent(value)}&limit=5`);
      const data = await response.json();
      setResults(data);
    } catch (error) {
      console.error("검색 실패:", error);
    }
  };

  return (
    <div>
      <input 
        type="text" 
        value={query} 
        onChange={handleSearch} 
        placeholder="가수명이나 곡 제목을 입력하세요" 
      />
      <ul>
        {results.map((song) => (
          <li key={song.song_id}>
            {song.title} - {song.artist}
            <button onClick={() => console.log("선택된 곡 ID:", song.song_id)}>
              제작하기
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}