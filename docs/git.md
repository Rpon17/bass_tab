cd C:\bass_project

# (선택) 실수로 clone된 폴더 제거
Remove-Item -Recurse -Force .\bass_tab

git add .
git commit -m "DTO 기능까지만 만듬"

git remote add origin https://github.com/Rpon17/bass_tab.git
git push -u origin master
