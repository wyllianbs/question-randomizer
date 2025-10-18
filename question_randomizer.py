'''
UNIVERSIDADE FEDERAL DE SANTA CATARINA (UFSC)
Centro Tecnológico (CTC)
Departamento de Informática e Estatística (INE)
Projeto: Randomizador de Questões LaTeX
Prof. Wyllian Bezerra da Silva
'''

import os
import re
import random
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from abc import ABC, abstractmethod


class Question:
    """Representa uma questão individual."""

    def __init__(self, content: str, source_file: str) -> None:
        self.content: str = content
        self.source_file: str = source_file

    def is_multiple_choice(self) -> bool:
        """Verifica se a questão é de múltipla escolha."""
        return r'\begin{answerlist}' in self.content and (
            r'\ti' in self.content or r'\di' in self.content
        )

    def randomize(self) -> str:
        """Retorna a questão randomizada (se aplicável)."""
        if self.is_multiple_choice():
            return self._randomize_alternatives()
        return self.content

    def _randomize_alternatives(self) -> str:
        """Randomiza as alternativas de uma questão de múltipla escolha."""
        answerlist_pattern: str = r'\\begin\{answerlist\}.*?\\end\{answerlist\}'
        match: Optional[re.Match[str]] = re.search(answerlist_pattern, self.content, re.DOTALL)

        if not match:
            return self.content

        answerlist_block: str = match.group(0)

        # Extrair alternativas
        alt_pattern: str = r'(\\[td]i\s+.*?)(?=\\[td]i|\s*\\end\{answerlist\})'
        alternatives: List[str] = re.findall(alt_pattern, answerlist_block, re.DOTALL)

        if not alternatives:
            return self.content

        # Separar gabarito das outras alternativas
        gabarito: Optional[str] = None
        other_alts: List[str] = []

        for alt in alternatives:
            if alt.strip().startswith(r'\di'):
                gabarito = alt
            else:
                other_alts.append(alt)

        # Randomizar
        random.shuffle(other_alts)

        # Inserir gabarito em posição aleatória
        if gabarito:
            insert_pos: int = random.randint(0, len(other_alts))
            other_alts.insert(insert_pos, gabarito)

        # Reconstruir o bloco answerlist
        header_match: Optional[re.Match[str]] = re.search(r'\\begin\{answerlist\}[^\n]*\n', answerlist_block)
        header: str = header_match.group(0) if header_match else (
            r'\begin{answerlist}[label={\texttt{\Alph*}.},leftmargin=*]' + '\n'
        )

        new_answerlist: str = header
        for alt in other_alts:
            new_answerlist += '    ' + alt.strip() + '\n'
        new_answerlist += r'\end{answerlist}'

        # Substituir no texto da questão
        return self.content.replace(answerlist_block, new_answerlist)


class QuestionFile:
    """Representa um arquivo .tex contendo questões."""

    def __init__(self, filepath: str) -> None:
        self.filepath: str = filepath
        self.filename: str = Path(filepath).name
        self.relative_path: Optional[Path] = None  # Será definido pela QuestionDatabase
        self.questions: List[Question] = []
        self._load_questions()

    def _load_questions(self) -> None:
        """Carrega todas as questões do arquivo."""
        with open(self.filepath, 'r', encoding='utf-8') as f:
            content: str = f.read()

        # Padrão: \needspace{<num>\baselineskip}\n\item \rtask
        pattern: str = r'\\needspace\{\d+\\baselineskip\}\s*\\item\s+\\rtask'
        matches: List[re.Match[str]] = list(re.finditer(pattern, content))

        for i, match in enumerate(matches):
            start: int = match.start()
            end: int = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            question_text: str = content[start:end].strip()
            self.questions.append(Question(question_text, self.filepath))

    def get_question_count(self) -> int:
        """Retorna o número de questões no arquivo."""
        return len(self.questions)

    def __repr__(self) -> str:
        count: int = self.get_question_count()
        question_word: str = "questão" if count == 1 else "questões"
        return f"QuestionFile('{self.filename}', {count} {question_word})"


class QuestionDatabase:
    """Gerencia o banco de dados de questões (diretório com arquivos .tex)."""

    def __init__(self, db_dir: str) -> None:
        self.db_dir: str = db_dir
        self.files: List[QuestionFile] = []
        self._load_files()

    def _load_files(self) -> None:
        """Carrega todos os arquivos .tex do diretório (recursivamente)."""
        db_path: Path = Path(self.db_dir)

        if not db_path.exists():
            raise FileNotFoundError(f"Diretório '{self.db_dir}' não encontrado.")

        # Busca recursiva usando rglob
        tex_files: List[Path] = sorted(db_path.rglob("*.tex"))

        if not tex_files:
            print(f"⚠ Nenhum arquivo .tex encontrado em '{self.db_dir}'")
            return

        print(f"📂 Buscando em: {db_path.absolute()}\n")

        for tex_file in tex_files:
            try:
                qf: QuestionFile = QuestionFile(str(tex_file))
                if qf.get_question_count() > 0:
                    # Calcula o caminho relativo ao diretório base
                    qf.relative_path = tex_file.relative_to(db_path)
                    self.files.append(qf)

                    # Exibe o caminho relativo para melhor visualização
                    display_path: str = str(qf.relative_path)
                    count: int = qf.get_question_count()
                    question_word: str = "questão" if count == 1 else "questões"
                    print(f"  ✓ {display_path:<40} - {count} {question_word}")
            except Exception as e:
                print(f"  ✗ Erro ao processar {tex_file.name}: {e}")

        if not self.files:
            print(f"\n⚠ Nenhuma questão válida encontrada nos arquivos .tex")

    def get_total_questions(self) -> int:
        """Retorna o número total de questões disponíveis."""
        return sum(qf.get_question_count() for qf in self.files)

    def get_file_count(self) -> int:
        """Retorna o número de arquivos carregados."""
        return len(self.files)

    def select_questions(self, num_questions: int) -> List[Question]:
        """Seleciona questões com distribuição uniforme."""
        if not self.files:
            return []

        total_available: int = self.get_total_questions()
        num_files: int = self.get_file_count()

        print(f"\n📊 Estatísticas:")
        print(f"  Total de arquivos: {num_files}")
        print(f"  Total de questões disponíveis: {total_available}")
        print(f"  Questões a selecionar: {num_questions}\n")

        selected: List[Question] = []

        # Criar lista de todas as questões com suas referências
        all_questions: List[Question] = []
        for qf in self.files:
            all_questions.extend(qf.questions)

        # Embaralhar
        random.shuffle(all_questions)

        # Se queremos menos questões que arquivos, priorizar diversidade
        if num_questions <= num_files:
            selected_files: Set[str] = set()
            for question in all_questions:
                if question.source_file not in selected_files:
                    selected.append(question)
                    selected_files.add(question.source_file)
                    if len(selected) >= num_questions:
                        break
        else:
            # Calcular proporção para cada arquivo
            file_selection: Dict[str, int] = {}
            remaining: int = num_questions

            for qf in self.files:
                proportion: float = qf.get_question_count() / total_available
                num_to_select: int = max(1, round(proportion * num_questions))
                num_to_select = min(num_to_select, qf.get_question_count(), remaining)
                file_selection[qf.filepath] = num_to_select
                remaining -= num_to_select

            # Ajustar se necessário
            while remaining > 0:
                for qf in self.files:
                    if file_selection[qf.filepath] < qf.get_question_count():
                        file_selection[qf.filepath] += 1
                        remaining -= 1
                        if remaining == 0:
                            break

            # Selecionar questões de cada arquivo
            for qf in self.files:
                num_to_select: int = file_selection[qf.filepath]
                selected_from_file: List[Question] = random.sample(qf.questions, num_to_select)
                selected.extend(selected_from_file)

        # Embaralhar ordem final
        random.shuffle(selected)
        return selected[:num_questions]


class OutputWriter:
    """Responsável por escrever o arquivo de saída."""

    def __init__(self, output_file: str) -> None:
        self.output_file: str = output_file

    def write(self, questions: List[Question]) -> None:
        """Escreve as questões randomizadas no arquivo de saída."""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for question in questions:
                randomized_content: str = question.randomize()
                f.write(randomized_content)
                f.write('\n\n\n')

        print(f"\n✓ Arquivo '{self.output_file}' gerado com sucesso!")
        count: int = len(questions)
        question_word: str = "questão" if count == 1 else "questões"
        print(f"  Total de {question_word}: {count}")


class UserInterface:
    """Interface com o usuário para entrada de dados."""

    @staticmethod
    def get_output_file() -> str:
        """Solicita o nome do arquivo de saída."""
        output_file: str = input("Nome/path do arquivo de saída [default: questions.tex]: ").strip()
        return output_file if output_file else "questions.tex"

    @staticmethod
    def get_database_directory() -> str:
        """Solicita o diretório do banco de questões."""
        db_dir: str = input("Diretório contendo as questões [default: ./db]: ").strip()
        return db_dir if db_dir else "db"

    @staticmethod
    def get_number_of_questions(total_available: int) -> int:
        """Solicita o número de questões com validação."""
        while True:
            prompt: str = f"Número total de questões a selecionar [default: 10; disponível: {total_available}]: "
            num_str: str = input(prompt).strip()

            num_questions: int
            if not num_str:
                num_questions = 10
            else:
                try:
                    num_questions = int(num_str)
                except ValueError:
                    print("❌ Valor inválido. Digite um número inteiro.")
                    continue

            if num_questions > total_available:
                print(f"\n⚠ Erro: Quantidade solicitada ({num_questions}) "
                      f"é maior que o total disponível ({total_available}).")
                print("Por favor, escolha um número menor ou igual ao total disponível.\n")
                continue

            if num_questions <= 0:
                print("\n⚠ Erro: O número de questões deve ser maior que zero.\n")
                continue

            return num_questions

    @staticmethod
    def print_header() -> None:
        """Exibe o cabeçalho do programa."""
        print("=" * 60)
        print("RANDOMIZADOR DE QUESTÕES LaTeX")
        print("=" * 60)
        print()

    @staticmethod
    def print_configuration(output_file: str, db_dir: str, num_questions: int) -> None:
        """Exibe a configuração escolhida."""
        print("\n" + "-" * 60)
        print("⚙️  Configuração:")
        print(f"  Arquivo de saída: {output_file}")
        print(f"  Diretório: {db_dir}")
        print(f"  Questões a selecionar: {num_questions}")
        print("-" * 60 + "\n")


class QuestionRandomizer:
    """Classe principal que coordena o processo de randomização."""

    def __init__(self) -> None:
        self.ui: UserInterface = UserInterface()
        self.database: Optional[QuestionDatabase] = None
        self.writer: Optional[OutputWriter] = None

    def run(self) -> None:
        """Executa o fluxo principal do programa."""
        try:
            # Exibir cabeçalho
            self.ui.print_header()

            # Obter configurações do usuário
            output_file: str = self.ui.get_output_file()
            db_dir: str = self.ui.get_database_directory()

            # Carregar banco de dados
            print("\n" + "-" * 60)
            print("📚 Carregando questões...\n")
            self.database = QuestionDatabase(db_dir)

            if self.database.get_file_count() == 0:
                print("\n❌ Nenhuma questão encontrada!")
                return

            # Mostrar total disponível e solicitar número de questões
            total_available: int = self.database.get_total_questions()
            print(f"\n💡 Total de questões disponíveis: {total_available}")
            print("-" * 60 + "\n")

            num_questions: int = self.ui.get_number_of_questions(total_available)

            # Exibir configuração
            self.ui.print_configuration(output_file, db_dir, num_questions)

            # Selecionar questões
            print("🔀 Selecionando questões...")
            selected_questions: List[Question] = self.database.select_questions(num_questions)

            if not selected_questions:
                print("❌ Nenhuma questão pôde ser selecionada!")
                return

            # Processar e escrever saída
            print("⚙️  Processando questões (randomizando alternativas)...")
            self.writer = OutputWriter(output_file)
            self.writer.write(selected_questions)

        except FileNotFoundError as e:
            print(f"\n❌ Erro: {e}")
        except Exception as e:
            print(f"\n❌ Erro inesperado: {e}")
            import traceback
            traceback.print_exc()


def main() -> None:
    """Função de entrada do programa."""
    randomizer: QuestionRandomizer = QuestionRandomizer()
    randomizer.run()


if __name__ == "__main__":
    main()
