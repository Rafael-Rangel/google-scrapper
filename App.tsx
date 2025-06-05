import { useState } from 'react'
import './App.css'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { Label } from './components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './components/ui/card'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './components/ui/alert-dialog'
import { Loader2, MapPin, Phone, Star } from 'lucide-react'

interface Estabelecimento {
  nome: string
  endereco: string
  telefone: string
  avaliacao: number | null
  fonte: string
}

function App() {
  const [tipo, setTipo] = useState('')
  const [regiao, setRegiao] = useState('')
  const [quantidade, setQuantidade] = useState('10')
  const [fonte, setFonte] = useState('google_maps')
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [estabelecimentos, setEstabelecimentos] = useState<Estabelecimento[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [existingCount, setExistingCount] = useState(0)
  const [modo, setModo] = useState('novo')

  const iniciarBusca = async (modoSelecionado = 'novo') => {
    setLoading(true)
    setError(null)
    setEstabelecimentos([])
    setJobId(null)
    setStatus('iniciando')
    setModo(modoSelecionado)

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tipo,
          regiao,
          quantidade: parseInt(quantidade),
          fonte,
          modo: modoSelecionado,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao iniciar busca')
      }

      // Verificar se precisa de confirmação (resultados existentes)
      if (data.status === 'confirm') {
        setShowConfirmDialog(true)
        setExistingCount(data.existing_count)
        setLoading(false)
        return
      }

      setJobId(data.job_id)
      setStatus('pendente')
      verificarStatus(data.job_id, data.tipo, data.regiao, modoSelecionado)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
      setLoading(false)
    }
  }

  const verificarStatus = async (id: string, tipo?: string, regiao?: string, modoAtual?: string) => {
    try {
      const url = new URL(`/api/search/${id}`, window.location.origin);
      url.searchParams.append('quantidade', quantidade);
      
      if (tipo) url.searchParams.append('tipo', tipo);
      if (regiao) url.searchParams.append('regiao', regiao);
      if (modoAtual) url.searchParams.append('modo', modoAtual);
      
      const response = await fetch(url.toString())
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao verificar status')
      }

      setStatus(data.status)

      if (data.status === 'completed') {
        setEstabelecimentos(data.estabelecimentos || [])
        setLoading(false)
      } else {
        // Continuar verificando a cada 3 segundos
        setTimeout(() => verificarStatus(id), 3000)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6 text-center">Buscador de Estabelecimentos</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4">Parâmetros de Busca</h2>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="tipo">Tipo de Estabelecimento</Label>
              <Input
                id="tipo"
                placeholder="Ex: farmácia, supermercado, padaria"
                value={tipo}
                onChange={(e) => setTipo(e.target.value)}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="regiao">Região</Label>
              <Input
                id="regiao"
                placeholder="Ex: Campo Grande, Rio de Janeiro"
                value={regiao}
                onChange={(e) => setRegiao(e.target.value)}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="quantidade">Quantidade de Resultados</Label>
              <Input
                id="quantidade"
                type="number"
                min="1"
                max="50"
                value={quantidade}
                onChange={(e) => setQuantidade(e.target.value)}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="fonte">Fonte de Dados</Label>
              <Select value={fonte} onValueChange={setFonte}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione uma fonte" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="google_maps">Google Maps</SelectItem>
                  <SelectItem value="paginas_amarelas">Páginas Amarelas</SelectItem>
                  <SelectItem value="apontador">Apontador</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <Button 
              className="w-full mt-2" 
              onClick={() => iniciarBusca()}
              disabled={loading || !tipo || !regiao}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Buscando...
                </>
              ) : (
                'Buscar Estabelecimentos'
              )}
            </Button>
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4">Status da Busca</h2>
          
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md mb-4">
              {error}
            </div>
          )}
          
          {status && (
            <div className="mb-4">
              <p className="font-medium">Status atual: 
                <span className={`ml-2 ${
                  status === 'completed' ? 'text-green-600' : 
                  status === 'pendente' || status === 'iniciando' ? 'text-amber-600' : 
                  'text-blue-600'
                }`}>
                  {status === 'completed' ? 'Concluído' : 
                   status === 'pendente' ? 'Em processamento' : 
                   status === 'iniciando' ? 'Iniciando busca' : 
                   status}
                </span>
              </p>
              
              {loading && (
                <div className="flex items-center mt-2">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <p className="text-sm text-gray-500">
                    {status === 'iniciando' ? 'Iniciando busca...' : 
                     status === 'pendente' ? 'Processando resultados...' : 
                     'Carregando...'}
                  </p>
                </div>
              )}
            </div>
          )}
          
          {estabelecimentos.length > 0 && (
            <div>
              <p className="font-medium text-green-600 mb-2">
                {estabelecimentos.length} estabelecimento(s) encontrado(s)
              </p>
              <p className="text-sm text-gray-500">
                Fonte: {estabelecimentos[0].fonte}
              </p>
            </div>
          )}
          
          {!loading && !status && !error && (
            <p className="text-gray-500">
              Preencha os parâmetros e clique em "Buscar Estabelecimentos" para iniciar.
            </p>
          )}
        </div>
      </div>
      
      {estabelecimentos.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold mb-4">Resultados</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {estabelecimentos.map((estabelecimento, index) => (
              <Card key={index} className="overflow-hidden">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">{estabelecimento.nome}</CardTitle>
                  {estabelecimento.avaliacao && (
                    <div className="flex items-center">
                      <Star className="h-4 w-4 fill-yellow-400 text-yellow-400 mr-1" />
                      <span className="text-sm font-medium">{estabelecimento.avaliacao}</span>
                    </div>
                  )}
                </CardHeader>
                
                <CardContent className="space-y-2 pb-2">
                  <div className="flex items-start">
                    <MapPin className="h-4 w-4 text-gray-500 mr-2 mt-0.5" />
                    <span className="text-sm">{estabelecimento.endereco}</span>
                  </div>
                  
                  <div className="flex items-center">
                    <Phone className="h-4 w-4 text-gray-500 mr-2" />
                    <span className="text-sm">{estabelecimento.telefone}</span>
                  </div>
                </CardContent>
                
                <CardFooter className="pt-2 text-xs text-gray-500">
                  Fonte: {estabelecimento.fonte}
                </CardFooter>
              </Card>
            ))}
          </div>
        </div>
      )}
      
      {/* Diálogo de confirmação para resultados existentes */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Resultados existentes encontrados</AlertDialogTitle>
            <AlertDialogDescription>
              Já existem {existingCount} resultados para "{tipo}" em "{regiao}". 
              O que deseja fazer?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setLoading(false)}>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => iniciarBusca('sobrescrever')}>
              Sobrescrever
            </AlertDialogAction>
            <AlertDialogAction onClick={() => iniciarBusca('juntar')}>
              Juntar (sem duplicatas)
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default App
