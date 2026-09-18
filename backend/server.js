const express = require('express');
const cors = require('cors');
const app = express();
app.use(cors()); 
app.use(express.json());
let data = [];
app.post('/api/data', (req,res)=>{
  if(req.headers['x-api-key']!=='PEGINTI_SECRET_2024') return res.status(401).send('Unauthorized');
  data.push({...req.body, date: new Date()});
  console.log('SYNC:', req.body); 
  res.json({ok:true});
});
app.get('/api/data',(req,res)=>res.json(data));
app.listen(3001,()=>console.log('API morgue sur http://localhost:3001'));
