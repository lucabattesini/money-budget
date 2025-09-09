import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Portal, Combobox, useFilter, useListCollection } from "@chakra-ui/react";
import { Toaster } from "../components/ui/toaster";
import { getAllCategories, insertNewTransaction } from "../api/endpoints";
import customToaster from "../utils/customToaster"
import { SpinnerLoading } from "../utils/loadingComponent";
// tirar seta para baixo

export default function ReportExpense() {
    const [loading, setLoading] = useState(true)
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [selectCategoryId, setSelectCategoryId] = useState("");
    const [organizedCategories, setOrganizedCategories] = useState([])

    const { contains } = useFilter({ sensitivity: "base" })
    const { collection, filter } = useListCollection({
        initialItems: organizedCategories,
        filter: (items, query) => {
            if (!query) {
                return items
            }
            return contains(items, query)
        }
        //itemToString: (item) => item.label,
        //itemToValue: (item) => item.value
    })

    useEffect(() => {
        getAllCategories().then(
            data => {
                const organized = data.map((category) => ({
                label: category.name,
                value: String(category.id)
                }));
                setOrganizedCategories(organized);
                setLoading(false)
            }
        )
    }, []);

    const handleSubmit = () => {
        const formatedValue = value * 100
        const payload = {
            label: description,
            value: parseInt(formatedValue),
            category: String(selectCategoryId)
        };

        if (!value || value === 0 ) {
            customToaster("Error", "error", "The amount value need to be bigger than 0")

            return;
        }

        if (!description) {
            customToaster("Error", "error", "You need to give a description to your transaction")
            return;
        }

        if (!selectCategoryId) {
            customToaster("Error", "error", "You need to select a category to your transaction")
            return;
        }

        insertNewTransaction(payload)
            .then(data => {
                if (data.status === 201 || data.status === 200) {
                    customToaster("Accepted", "success", "Your transaction is saved!")

                    setvalue("");
                    setDescription("");
                    setSelectedCategory("Select category");

                } else {
                    customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
                }
            })
            .catch(error => {
                customToaster("Error", "error", "Some error ocurred to report your transaction, please try again later")
            })
    }


    


    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >    
                <Toaster/>
                
                <Heading size={"2xl"}>
                    Report Expense
                </Heading>

                <Input 
                type="number" placeholder="Amount" variant="outline" 
                value={value} onChange={(e) => setvalue(e.target.value)}
                />

                <Input
                placeholder="Description" variant="outline" maxLength={25}
                value={description} onChange={(e) => setDescription(e.target.value)}
                />
                
                {loading && <SpinnerLoading/>}
                {!loading && 
                    <Combobox.Root
                    collection={collection}
                    onInputValueChange={(e) => filter(e.inputValue)}>
                        <Combobox.Label> Select Category </Combobox.Label>
                        <Combobox.Control>
                            <Combobox.Input placeholder="Select category"/>
                            <Combobox.IndicatorGroup>
                                <Combobox.ClearTrigger/>
                                <Combobox.Trigger />
                            </Combobox.IndicatorGroup>
                        </Combobox.Control>
                        <Portal>
                            <Combobox.Positioner>
                                <Combobox.Content>
                                    <Combobox.Empty>No items found</Combobox.Empty>
                                    {collection.items.map((item) => (
                                        <Combobox.Item item={item} key={item.value}>
                                            {item.label}
                                            <Combobox.Indicator />
                                        </Combobox.Item>
                                    ))}
                                </Combobox.Content>
                            </Combobox.Positioner>
                        </Portal>
                    </Combobox.Root>
                }
                
                <Button onClick={handleSubmit}>
                    Submit
                </Button>
            </Stack>
        </Center>
    );
}

const frameworks = [
  { label: "React", value: "react" },
  { label: "Solid", value: "solid" },
  { label: "Vue", value: "vue" },
  { label: "Angular", value: "angular" },
  { label: "Svelte", value: "svelte" },
  { label: "Preact", value: "preact" },
  { label: "Qwik", value: "qwik" },
  { label: "Lit", value: "lit" },
  { label: "Alpine.js", value: "alpinejs" },
  { label: "Ember", value: "ember" },
  { label: "Next.js", value: "nextjs" },
]