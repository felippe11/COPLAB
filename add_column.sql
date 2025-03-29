-- Adicionar a coluna com valor padrão
ALTER TABLE configuracoes ADD COLUMN pontuacao_minima INTEGER DEFAULT 10;

-- Fazer update em todos os registros existentes
UPDATE configuracoes SET pontuacao_minima = 10 WHERE pontuacao_minima IS NULL;

-- Tornar a coluna NOT NULL
ALTER TABLE configuracoes ALTER COLUMN pontuacao_minima SET NOT NULL; 